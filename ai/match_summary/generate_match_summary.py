"""Generate a two-part auto-written match summary.

Reads match_stats, substitutes, formation, team_shape, progressive_map, and
pass_network output (both teams, where applicable) plus tactical_findings.json
for one match, assembles them into model context, and calls Claude twice to
produce:

1. A **structured outcome section** (headline, key stats, standout performers),
   via the Messages API's structured-output mode (`client.messages.parse`
   against a Pydantic schema) — not a plain completion parsed as JSON. The
   model may draw on any of the six extractor source files; every number it
   surfaces must be copied verbatim from a field in that data, never computed
   or estimated. `source_field` on each stat/performer records the exact
   field it came from, so grounding is spot-checkable.
2. A **structured tactics section** — `sentences: [{text, finding_ids}]`,
   also via `client.messages.parse` (DATA-SPEC-v2 Part 4). The model receives
   only findings from `tactical_findings.json` that carry a non-null `claim`
   (`libs/statsbomb/derive_tactical_findings.py`, Part 2) — no raw extractor
   JSON. It describes what happened in the match, in order, picking the most
   notable findings; every sentence cites the finding ID(s) whose `claim` it
   states, word for word; the words between claims come only from
   `tactical_definitions.CONNECTIVES`. `check_grounding()` then verifies this
   mechanically — see its own docstring.

Per DATA-SPEC.md, the outcome section consumes only the six extractors that
exist today (Shape & structure, Progression style). Pressing/PPDA, buildup-
chain-to-shot, transition, and set-piece extractors are out of scope (Module 2).

Public API:
    load_match_context(match_id, data_dir) -> dict
    generate_outcome_section(context, match_label, competition) -> OutcomeSection
    generate_tactics_section(context, match_label, competition) -> dict
    check_grounding(sentences, findings) -> dict
    generate_match_summary(match_id) -> dict
    main()

JSON output shape (match_summary.json):
    {
      "outcome": {
        "headline": str,
        "key_stats": [
          {"label": str, "value": str, "source_field": str}
        ],
        "standout_performers": [
          {"player": str, "team": str, "reason": str, "source_field": str}
        ]
      },
      "tactics": {
        "prose": str,
        "claims": [{"text": str, "finding_ids": [str]}]
      },
      "metadata": {
        "match_id": int,
        "home_team": str,
        "away_team": str,
        "competition": str,
        "match_label": str,
        "models": {"outcome": str, "tactics": str},
        "effort": {"outcome": str, "tactics": str},
        "source_files": {
          "match_stats": str,
          "substitutes": str,
          "formation": {"home": str, "away": str},
          "team_shape": {"home": str, "away": str},
          "progressive_map": {"home": str, "away": str},
          "pass_network": {"home": str, "away": str},
          "tactical_findings": str
        }
      }
    }
Written to: ai/match_summary/output/{match_id}/match_summary.json

check_grounding()'s report is written separately to
ai/match_summary/output/{match_id}/grounding_report.json on every run —
see check_grounding()'s own docstring for its shape and main()'s for the
publish/exit-code behavior on failure.
"""

import json
import re
import sys
from pathlib import Path

import anthropic
from dotenv import load_dotenv
from pydantic import BaseModel

from statsbomb.tactical_definitions import BANNED_TERMS, CAUSAL_TERMS, CONNECTIVES
from statsbomb.utils import fetch_match_info, resolve_match

# Finding types that carry a minute — a sequence connective (CONNECTIVES
# "sequence") between claims is only allowed when at least one cited finding
# is one of these (DATA-SPEC-v2's linking rule).
_MINUTE_BEARING_TYPES = frozenset({"goal", "substitution", "formation_change", "role_change", "game_state", "change"})

# Per-section model + effort. Claude 5-family models reject non-default
# temperature/top_p/top_k (400), so effort is the sampling-adjacent knob instead —
# see SPEC.md decision log, "2026-09-15 — Sampling controls unavailable on
# Claude 5-family."
#
# Routing chosen from ai/match_summary/output/3943043/comparison-3943043.md (5 measured cells on
# match 3943043, n = 1 each). It is a DEFAULT, to be revisited once the eval system
# (Module 3) exists: the comparison recorded errors by manual read, not a scored eval.
OUTCOME_MODEL = "claude-sonnet-5"
OUTCOME_EFFORT = "low"  # verbatim extraction + light editorial selection; 0 errors in the comparison
TACTICS_MODEL = "claude-opus-5"
TACTICS_EFFORT = "medium"  # synthesis across 3 sources; fewest errors in the comparison

# Thinking tokens count toward max_tokens. The comparison ran both sections at
# 16000; the tactics call alone used up to ~2.4k output tokens on Opus, so the
# old 1500 cap would truncate it.
MAX_TOKENS = 16000


class KeyStat(BaseModel):
    """One stat surfaced in the structured outcome section.

    Attributes:
        label (str): Display label, e.g. "xG".
        value (str): The stat's value, copied verbatim from the source JSON
            (as a string so formatting like "58%" or "2.1" round-trips as-is).
        source_field (str): Dotted/bracketed path to the exact source JSON
            field this value was copied from, e.g. "match_stats.rows[7].home_value".
    """

    label: str
    value: str
    source_field: str


class StandoutPerformer(BaseModel):
    """One player surfaced in the structured outcome section.

    Attributes:
        player (str): Player's display name.
        team (str): Team name.
        reason (str): Why this player was selected (editorial, not a fact claim).
        source_field (str): Dotted/bracketed path to the source JSON field(s)
            grounding this selection.
    """

    player: str
    team: str
    reason: str
    source_field: str


class OutcomeSection(BaseModel):
    """The full structured outcome section — the schema passed to structured outputs.

    Attributes:
        headline (str): One-sentence summary of the match outcome.
        key_stats (list[KeyStat]): 3-8 stats characterizing the match.
        standout_performers (list[StandoutPerformer]): 2-5 notable players.
    """

    headline: str
    key_stats: list[KeyStat]
    standout_performers: list[StandoutPerformer]


class Sentence(BaseModel):
    """One sentence of the tactics section, with its grounding.

    Attributes:
        text (str): The sentence as written. Must contain, word for word,
            every cited finding's `claim`, joined only by words from
            `tactical_definitions.CONNECTIVES` (DATA-SPEC-v2's linking rule).
        finding_ids (list[str]): IDs (from tactical_findings.json) of every
            finding this sentence states. At least one.
    """

    text: str
    finding_ids: list[str]


class Sentences(BaseModel):
    """The tactics section's structured-output schema — an ordered list of sentences.

    Attributes:
        sentences (list[Sentence]): The tactics section, in narration order.
    """

    sentences: list[Sentence]


def _team_slug(team: str) -> str:
    """Slugify a team name the way extract_formation.py / extract_team_shape.py do.

    Args:
        team (str): Team name, e.g. "Spain".

    Returns:
        str: Lowercase, non-alphanumeric runs collapsed to underscores, e.g. "spain".
    """
    return re.sub(r"[^a-z0-9]+", "_", team.lower()).strip("_")


def _progressive_map_slug(team: str) -> str:
    """Slugify a team name the way extract_progressive_map.py does.

    Args:
        team (str): Team name, e.g. "Spain".

    Returns:
        str: Lowercase with spaces replaced by underscores, e.g. "spain".
    """
    return team.lower().replace(" ", "_")


def _load_json(path: Path) -> dict:
    """Load one JSON file, raising a clear error if it doesn't exist yet.

    Args:
        path (Path): Path to the extractor output JSON.

    Returns:
        dict: Parsed JSON content.

    Raises:
        FileNotFoundError: If the file doesn't exist — the extractor that
            produces it needs to be run first.
    """
    if not path.exists():
        raise FileNotFoundError(
            f"{path} does not exist. Run its extractor's main() for this match_id first."
        )
    with open(path) as f:
        return json.load(f)


def load_match_context(match_id: int, data_dir: Path) -> dict:
    """Load the six existing extractors' JSON output for one match into a single dict.

    Reads match_stats.json and substitutes.json (match-level), plus
    formation_{slug}.json, team_shape_{slug}.json, progressive_map_{slug}.json,
    and pass_network_{team}.json for both home and away teams, plus the
    match-level tactical_findings.json (libs/statsbomb/derive_tactical_findings.py,
    DATA-SPEC-v2 Part 2). Home/away and team-name resolution come from
    match_stats.json, so it must exist first — every other file is located
    relative to those two names.

    Args:
        match_id (int): StatsBomb match ID.
        data_dir (Path): Match's data directory, e.g. data/euro-2024/{match_id}/.

    Returns:
        dict: {
            "match_stats": dict,
            "substitutes": dict,
            "formation": {"home": dict, "away": dict},
            "team_shape": {"home": dict, "away": dict},
            "progressive_map": {"home": dict, "away": dict},
            "pass_network": {"home": dict, "away": dict},
            "tactical_findings": dict,
            "home_team": str,
            "away_team": str,
        }

    Raises:
        FileNotFoundError: If any of the six extractors or
            derive_tactical_findings hasn't been run for this match yet.
    """
    match_stats = _load_json(data_dir / "match_stats.json")
    home_team = match_stats["home"]["team"]
    away_team = match_stats["away"]["team"]

    def per_team(filename_fn) -> dict:
        return {
            "home": _load_json(data_dir / filename_fn(home_team)),
            "away": _load_json(data_dir / filename_fn(away_team)),
        }

    return {
        "match_stats": match_stats,
        "substitutes": _load_json(data_dir / "substitutes.json"),
        "formation": per_team(lambda t: f"formation_{_team_slug(t)}.json"),
        "team_shape": per_team(lambda t: f"team_shape_{_team_slug(t)}.json"),
        "progressive_map": per_team(lambda t: f"progressive_map_{_progressive_map_slug(t)}.json"),
        "pass_network": per_team(lambda t: f"pass_network_{t}.json"),
        "tactical_findings": _load_json(data_dir / "tactical_findings.json"),
        "home_team": home_team,
        "away_team": away_team,
    }


def _build_client() -> anthropic.Anthropic:
    """Build an Anthropic client, loading ANTHROPIC_API_KEY from the repo's .env if present.

    load_dotenv() populates os.environ from data/../.env (repo root) without
    overriding any already-exported shell value; anthropic.Anthropic() then
    resolves credentials from the environment as usual. Never hardcode a key.

    Returns:
        anthropic.Anthropic: Client configured from the environment.
    """
    load_dotenv(Path(__file__).parents[2] / ".env")
    return anthropic.Anthropic()


def _effort_kwargs(effort: str | None) -> dict:
    """Build the optional ``output_config`` kwarg for a Messages API call.

    Args:
        effort (str | None): Effort level, or None for models that don't
            support the ``effort`` parameter (Haiku 4.5 rejects it).

    Returns:
        dict: ``{"output_config": {"effort": effort}}``, or ``{}`` when effort is None.
    """
    return {"output_config": {"effort": effort}} if effort is not None else {}


def _request_outcome(
    context: dict,
    match_label: str,
    competition: str,
    model: str,
    effort: str | None,
    max_tokens: int,
):
    """Send the outcome-section request and return the raw parsed response.

    Shared by generate_outcome_section() (which unwraps it) and the model/effort
    comparison harness (which needs ``usage`` and ``stop_reason`` too). Does no
    refusal handling — callers decide how to treat a non-"end_turn" stop.

    Args:
        context (dict): Output of load_match_context().
        match_label (str): e.g. "Spain vs England".
        competition (str): e.g. "UEFA Euro 2024".
        model (str): Model ID to call.
        effort (str | None): ``output_config.effort`` value, or None to omit it.
        max_tokens (int): Response token ceiling (thinking counts toward it).

    Returns:
        anthropic.types.ParsedMessage: The full response; ``parsed_output`` is
            the OutcomeSection.
    """
    client = _build_client()
    system = (
        f"You are generating the structured outcome section of an auto-written match "
        f"summary for {match_label} ({competition}).\n\n"
        "You are given six StatsBomb-derived JSON extracts for this match: "
        "match_stats, substitutes, formation (both teams), team_shape (both teams), "
        "progressive_map (both teams), and pass_network (both teams). These are the "
        "ONLY source of truth — do not use outside knowledge of this match.\n\n"
        "Produce:\n"
        "- headline: one sentence covering the final score and the standout outcome.\n"
        "- key_stats: 3-8 stats that best characterize the match. You choose WHICH "
        "stats matter (that's an editorial call), but every value must be copied "
        "exactly from a field in the provided JSON — never computed, estimated, or "
        "rounded differently than the source.\n"
        "- standout_performers: 2-5 players whose involvement is grounded in the "
        "provided JSON (goals/shots from match_stats, substitution timing from "
        "substitutes, progressive-action counts from progressive_map, pass volume "
        "from pass_network, etc.).\n\n"
        "For every key stat and performer, set source_field to the exact JSON path "
        "you pulled the value from, e.g. \"match_stats.rows[7].home_value\" or "
        "\"substitutes.teams.Spain[0].player\". If you can't point to a field, don't "
        "include the claim."
    )
    user_content = (
        "Source JSON (all six extractors, both teams):\n\n"
        + json.dumps(context, indent=2)
    )

    return client.messages.parse(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user_content}],
        output_format=OutcomeSection,
        **_effort_kwargs(effort),
    )


def generate_outcome_section(context: dict, match_label: str, competition: str) -> OutcomeSection:
    """Generate the structured outcome section via the Messages API's structured-output mode.

    Uses client.messages.parse() against the OutcomeSection Pydantic schema so
    the response shape is guaranteed — not a plain completion parsed as JSON.
    The model sees all six source files and selects which stats/performers to
    surface (an editorial call); every value it emits must be copied from a
    field in that data, and source_field records which one. Runs at
    OUTCOME_EFFORT ("low"): verbatim extraction plus light editorial
    selection doesn't need deep reasoning.

    Args:
        context (dict): Output of load_match_context().
        match_label (str): e.g. "Spain vs England".
        competition (str): e.g. "UEFA Euro 2024".

    Returns:
        OutcomeSection: Parsed, schema-validated outcome section.

    Raises:
        RuntimeError: If the model declines to answer (stop_reason == "refusal").
    """
    response = _request_outcome(
        context, match_label, competition, OUTCOME_MODEL, OUTCOME_EFFORT, MAX_TOKENS
    )
    if response.stop_reason == "refusal":
        raise RuntimeError(
            "Model declined to generate the outcome section "
            f"(stop_details={response.stop_details})."
        )
    return response.parsed_output


def _claimed_findings(context: dict) -> list[dict]:
    """The subset of tactical_findings.json's findings the model is allowed to see.

    DATA-SPEC-v2 Part 4 step 1: "sends findings with a non-null claim only" —
    a null-claim finding (e.g. a value-only one like team_width) cannot be
    cited alone, so there is nothing word-for-word for the model to state.

    Args:
        context (dict): Output of load_match_context().

    Returns:
        list[dict]: context["tactical_findings"]["findings"], filtered to claim is not None.
    """
    return [f for f in context["tactical_findings"]["findings"] if f["claim"] is not None]


def _request_tactics(
    context: dict,
    match_label: str,
    competition: str,
    model: str,
    effort: str | None,
    max_tokens: int,
):
    """Send the tactics-section request and return the raw response.

    Shared by generate_tactics_section() (which unwraps it) and the model/effort
    comparison harness (which needs ``usage`` and ``stop_reason`` too). Does no
    refusal handling — callers decide how to treat a non-"end_turn" stop.

    Args:
        context (dict): Output of load_match_context(). Only findings with a
            non-null claim (see _claimed_findings) are sent to the model — no
            raw extractor JSON, per DATA-SPEC-v2 seam rule 2.
        match_label (str): e.g. "Spain vs England".
        competition (str): e.g. "UEFA Euro 2024".
        model (str): Model ID to call.
        effort (str | None): ``output_config.effort`` value, or None to omit it.
        max_tokens (int): Response token ceiling (thinking counts toward it).

    Returns:
        anthropic.types.ParsedMessage: The full response; ``parsed_output`` is a Sentences.
    """
    client = _build_client()
    findings = _claimed_findings(context)

    system = (
        f"You are writing the tactics section of an auto-written match summary for "
        f"{match_label} ({competition}): what happened in the match, in order.\n\n"
        "You are given a list of findings, each already computed and labelled by code "
        "from StatsBomb data. Each finding has a `claim`: the exact clause that states "
        "it. These are the ONLY source of truth — you have not been given any raw "
        "match data, and you compute nothing yourself: no comparison, no sum, no label.\n\n"
        "Your job:\n"
        "- Select the most notable findings (higher `notability` first, but use "
        "judgement — a selection of findings that reads as a coherent account of the "
        "match beats a bare ranking) and put them in a sentence each, or joined into "
        "a sentence with another finding.\n"
        "- Every sentence must cite the id of every finding it states, in finding_ids.\n"
        "- Every sentence's text must contain each cited finding's claim word for "
        "word, exactly as given (case may differ only on a claim's very first letter, "
        "e.g. when it follows a connective mid-sentence).\n"
        "- The words between claims — joining two claims in one sentence, or starting "
        "a new sentence — may ONLY be one of these connectives, nothing else: "
        f"{sorted(CONNECTIVES['joining'])} to join without implying sequence, or "
        f"{sorted(CONNECTIVES['sequence'])} to show order — and a sequence connective "
        "is only allowed when at least one of the claims it connects comes from a "
        "finding with a minute (a goal, substitution, formation change, role change, "
        "game state, or change finding).\n"
        "- Never write a causal word (e.g. \"because\", \"led to\", \"so\", "
        "\"therefore\") or infer intent, fatigue, or morale — this section states "
        "what happened, not why.\n"
        "- Do not add any word of your own beyond a cited claim and the connectives "
        "above: no adjectives, no editorializing, no restating a number differently.\n\n"
        "Findings (id, type, team, claim, notability):\n\n"
        + json.dumps(
            [
                {"id": f["id"], "type": f["type"], "team": f["team"], "claim": f["claim"], "notability": f["notability"]}
                for f in findings
            ],
            indent=2,
        )
    )
    user_content = "Write the tactics section's sentences now."

    return client.messages.parse(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user_content}],
        output_format=Sentences,
        **_effort_kwargs(effort),
    )


def generate_tactics_section(context: dict, match_label: str, competition: str) -> dict:
    """Generate the structured tactics section: sentences grounded in findings only.

    Receives only tactical_findings.json's non-null-claim findings (DATA-SPEC-v2
    Part 2/4) — no raw extractor JSON, no match_stats, no event data. The model
    selects and orders findings into sentences; every sentence must cite the
    finding(s) it states and contain their `claim` word for word, joined only
    by `tactical_definitions.CONNECTIVES` under the linking rule. It computes no
    fact itself — comparisons, sums and labels are already in each claim.
    Causal explanation ("how the outcome happened") is out of scope for this
    spec; this section states what happened, in order, not why. Runs on
    TACTICS_MODEL at TACTICS_EFFORT: selecting and ordering findings into a
    coherent account benefits from a stronger model and deeper reasoning.

    Args:
        context (dict): Output of load_match_context().
        match_label (str): e.g. "Spain vs England".
        competition (str): e.g. "UEFA Euro 2024".

    Returns:
        dict: {"prose": str, "claims": [{"text": str, "finding_ids": [str]}]} —
            prose is every sentence's text joined with a space; claims is the
            model's own sentences list, serving as the claim map (an output
            now, not a hand-built table).

    Raises:
        RuntimeError: If the model declines to answer (stop_reason == "refusal").
    """
    response = _request_tactics(
        context, match_label, competition, TACTICS_MODEL, TACTICS_EFFORT, MAX_TOKENS
    )
    if response.stop_reason == "refusal":
        raise RuntimeError(
            f"Model declined to generate the tactics section (stop_details={response.stop_details})."
        )
    sentences = response.parsed_output.sentences
    return {
        "prose": " ".join(s.text for s in sentences),
        "claims": [s.model_dump() for s in sentences],
    }


def check_grounding(sentences: list[dict], findings: list[dict]) -> dict:
    """Mechanically verify every tactics sentence states only what its findings say.

    DATA-SPEC-v2 Part 4 step 5. A generation gate, not the eval (Module 3) —
    it checks that the model didn't add, alter, or misattribute a fact; it has
    no opinion on whether the right findings were chosen or whether the prose
    reads well.

    Per sentence, five independent checks:
      1. cites_valid_ids: finding_ids is non-empty, every id exists in
         ``findings``, and every cited finding has a non-null claim.
      2. claims_present: every cited (valid) finding's claim appears in the
         text word for word. The comparison is case-sensitive except the
         claim's first character, so a claim may open a sentence or follow a
         connective mid-sentence either way.
      3. leftover_clean (the "leftover check"): remove every claim matched in
         check 2 from the text, then remove every occurrence of a
         `tactical_definitions.CONNECTIVES` word/phrase from what's left.
         Nothing but punctuation and whitespace may remain — no digit, no
         name, no word the model added on its own.
      4. sequence_requires_minute_bearing: a sequence connective (CONNECTIVES
         "sequence": "then", "after", "before", "following", "meanwhile")
         appears in the leftover only if at least one cited finding's type is
         minute-bearing (goal, substitution, formation_change, role_change,
         game_state, change).
      5. no_banned_terms: no `tactical_definitions.CAUSAL_TERMS` or
         `BANNED_TERMS` word anywhere in the sentence's full text (CAUSAL_TERMS
         is a subset of BANNED_TERMS, checked together).

    A sentence passes only if all five pass. The report fails
    ("publishable": False) if any sentence fails any check — exactly what
    failed and the leftover text are kept per sentence, so a failure shows
    precisely what the model added.

    Args:
        sentences (list[dict]): [{"text": str, "finding_ids": [str]}, ...] —
            typically ``generate_tactics_section(...)["claims"]``.
        findings (list[dict]): Every finding (not just claimed ones) from
            tactical_findings.json, so an unknown id is distinguishable from
            a null-claim one.

    Returns:
        dict: {
            "publishable": bool,
            "sentences": [
                {
                    "text": str, "finding_ids": [str], "passed": bool,
                    "checks": {
                        "cites_valid_ids": bool, "claims_present": bool,
                        "leftover_clean": bool,
                        "sequence_requires_minute_bearing": bool,
                        "no_banned_terms": bool,
                    },
                    "unknown_ids": [str], "missing_claim_ids": [str],
                    "leftover_text": str,
                }
            ],
        }
    """
    findings_by_id = {f["id"]: f for f in findings}
    banned_pattern = re.compile(
        "|".join(re.escape(t) for t in sorted(BANNED_TERMS | CAUSAL_TERMS, key=len, reverse=True)),
        re.IGNORECASE,
    )
    all_connectives_pattern = re.compile(
        "|".join(re.escape(c) for c in sorted(CONNECTIVES["joining"] | CONNECTIVES["sequence"], key=len, reverse=True)),
        re.IGNORECASE,
    )
    sequence_pattern = re.compile(
        "|".join(re.escape(c) for c in sorted(CONNECTIVES["sequence"], key=len, reverse=True)),
        re.IGNORECASE,
    )

    sentence_reports = []
    for sentence in sentences:
        text = sentence["text"]
        finding_ids = sentence.get("finding_ids", [])

        unknown_ids = [fid for fid in finding_ids if fid not in findings_by_id]
        null_claim_ids = [fid for fid in finding_ids if fid in findings_by_id and findings_by_id[fid]["claim"] is None]
        check1 = len(finding_ids) > 0 and not unknown_ids and not null_claim_ids

        valid_ids = [fid for fid in finding_ids if fid in findings_by_id and findings_by_id[fid]["claim"] is not None]
        missing_claim_ids = []
        remaining = text
        for fid in valid_ids:
            claim = findings_by_id[fid]["claim"]
            variants = {claim, claim[0].upper() + claim[1:], claim[0].lower() + claim[1:]} if claim else {claim}
            found = next((v for v in variants if v in remaining), None)
            if found is None:
                missing_claim_ids.append(fid)
            else:
                remaining = remaining.replace(found, "", 1)
        check2 = len(missing_claim_ids) == 0

        leftover_before_connectives = remaining
        leftover = all_connectives_pattern.sub("", remaining)
        check3 = not re.search(r"[A-Za-z0-9]", leftover)

        has_sequence_word = bool(sequence_pattern.search(leftover_before_connectives))
        cites_minute_bearing = any(
            fid in findings_by_id and findings_by_id[fid]["type"] in _MINUTE_BEARING_TYPES
            for fid in finding_ids
        )
        check4 = (not has_sequence_word) or cites_minute_bearing

        check5 = not banned_pattern.search(text)

        sentence_reports.append({
            "text": text,
            "finding_ids": finding_ids,
            "passed": check1 and check2 and check3 and check4 and check5,
            "checks": {
                "cites_valid_ids": check1,
                "claims_present": check2,
                "leftover_clean": check3,
                "sequence_requires_minute_bearing": check4,
                "no_banned_terms": check5,
            },
            "unknown_ids": unknown_ids,
            "missing_claim_ids": missing_claim_ids,
            "leftover_text": leftover,
        })

    return {
        "publishable": all(s["passed"] for s in sentence_reports),
        "sentences": sentence_reports,
    }


def generate_match_summary(match_id: int) -> dict:
    """Generate the full two-section match summary for one match.

    Loads the six extractors' JSON plus tactical_findings.json from
    data/euro-2024/{match_id}/, calls the model twice (structured outcome,
    then structured tactics), and assembles the result into the documented
    output shape. Does not run check_grounding or write grounding_report.json
    — that's main()'s job, since it's a separate output file.

    Args:
        match_id (int): StatsBomb match ID.

    Returns:
        dict: The full match_summary.json payload — see module docstring for shape.

    Raises:
        FileNotFoundError: If any of the six source extractors or
            derive_tactical_findings hasn't been run for this match yet.
    """
    data_dir = Path(__file__).parents[2] / "data" / "euro-2024" / str(match_id)
    context = load_match_context(match_id, data_dir)
    competition, _, match_label = fetch_match_info(match_id)

    outcome = generate_outcome_section(context, match_label, competition)
    tactics = generate_tactics_section(context, match_label, competition)

    home_team = context["home_team"]
    away_team = context["away_team"]

    return {
        "outcome": outcome.model_dump(),
        "tactics": tactics,
        "metadata": {
            "match_id": match_id,
            "home_team": home_team,
            "away_team": away_team,
            "competition": competition,
            "match_label": match_label,
            "models": {"outcome": OUTCOME_MODEL, "tactics": TACTICS_MODEL},
            "effort": {"outcome": OUTCOME_EFFORT, "tactics": TACTICS_EFFORT},
            "source_files": {
                "match_stats": "match_stats.json",
                "substitutes": "substitutes.json",
                "formation": {
                    "home": f"formation_{_team_slug(home_team)}.json",
                    "away": f"formation_{_team_slug(away_team)}.json",
                },
                "team_shape": {
                    "home": f"team_shape_{_team_slug(home_team)}.json",
                    "away": f"team_shape_{_team_slug(away_team)}.json",
                },
                "progressive_map": {
                    "home": f"progressive_map_{_progressive_map_slug(home_team)}.json",
                    "away": f"progressive_map_{_progressive_map_slug(away_team)}.json",
                },
                "pass_network": {
                    "home": f"pass_network_{home_team}.json",
                    "away": f"pass_network_{away_team}.json",
                },
                "tactical_findings": "tactical_findings.json",
            },
        },
    }


def main(match_id: int | None = None, out_dir: Path | None = None) -> None:
    """Generate the match summary for a match, write it, and gate it on grounding.

    Writes match_summary.json, then runs check_grounding() against the
    tactics section's sentences and every finding (not just claimed ones) in
    tactical_findings.json, and writes grounding_report.json on every run —
    pass or fail (DATA-SPEC-v2 Part 4 step 7). A failing report is written
    with "publishable": false, and this function exits the process non-zero
    so a failing generation can't silently ship.

    Args:
        match_id (int | None): StatsBomb match ID; defaults to Euro 2024 Final.
        out_dir (Path | None): Output directory; defaults to
            ai/match_summary/output/{match_id}/.

    Output: {out_dir}/match_summary.json, {out_dir}/grounding_report.json
    """
    if match_id is None:
        match_id = resolve_match("UEFA Euro", "2024", "Spain", "England")
    if out_dir is None:
        out_dir = Path(__file__).parent / "output" / str(match_id)
    out_dir.mkdir(parents=True, exist_ok=True)

    summary = generate_match_summary(match_id)

    out_path = out_dir / "match_summary.json"
    with open(out_path, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"Wrote match summary → {out_path}")
    print(f"  Headline: {summary['outcome']['headline']}")
    print(f"  {len(summary['outcome']['key_stats'])} key stats, "
          f"{len(summary['outcome']['standout_performers'])} standout performers")

    data_dir = Path(__file__).parents[2] / "data" / "euro-2024" / str(match_id)
    all_findings = _load_json(data_dir / "tactical_findings.json")["findings"]
    report = check_grounding(summary["tactics"]["claims"], all_findings)

    report_path = out_dir / "grounding_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)

    n_failed = sum(1 for s in report["sentences"] if not s["passed"])
    print(f"Wrote grounding report → {report_path} "
          f"({len(report['sentences']) - n_failed}/{len(report['sentences'])} sentences passed)")

    if not report["publishable"]:
        print("Grounding check FAILED — not publishable.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
