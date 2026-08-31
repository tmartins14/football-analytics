"""Generate a two-part auto-written match summary from six existing extractors' JSON.

Reads match_stats, substitutes, formation, team_shape, progressive_map, and
pass_network output (both teams, where applicable) for one match, assembles
them into model context, and calls Claude twice to produce:

1. A **structured outcome section** (headline, key stats, standout performers),
   via the Messages API's structured-output mode (`client.messages.parse`
   against a Pydantic schema) — not a plain completion parsed as JSON. The
   model may draw on any of the six source files; every number it surfaces
   must be copied verbatim from a field in that data, never computed or
   estimated. `source_field` on each stat/performer records the exact field
   it came from, so grounding is spot-checkable.
2. A **free-prose tactics section** (formations, shape, buildup), grounded
   *only* in the formation / team_shape / pass_network JSON (per SPEC.md —
   deliberately narrower than the outcome section's source set). The system
   prompt forbids claims — goals, cards, tactical role labels like "false 9"
   — that aren't literally present in those three files.

Per DATA-SPEC.md, this module consumes only the six extractors that exist
today (Shape & structure, Progression style). Pressing/PPDA, buildup-chain-
to-shot, transition, and set-piece extractors are out of scope (Module 2).

Public API:
    load_match_context(match_id, data_dir) -> dict
    generate_outcome_section(context, match_label, competition) -> OutcomeSection
    generate_tactics_section(context, match_label, competition) -> str
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
        "prose": str
      },
      "metadata": {
        "match_id": int,
        "home_team": str,
        "away_team": str,
        "competition": str,
        "match_label": str,
        "model": str,
        "source_files": {
          "match_stats": str,
          "substitutes": str,
          "formation": {"home": str, "away": str},
          "team_shape": {"home": str, "away": str},
          "progressive_map": {"home": str, "away": str},
          "pass_network": {"home": str, "away": str}
        }
      }
    }
Written to: data/euro-2024/{match_id}/match_summary.json
"""

import json
import re
from pathlib import Path

import anthropic
from dotenv import load_dotenv
from pydantic import BaseModel

from .utils import fetch_match_info, resolve_match

MODEL = "claude-sonnet-5"

# Tactics-section grounding is deliberately narrower than the outcome section's —
# see SPEC.md: "the prompt must constrain the model to the formation /
# team-shape / pass-network JSON it's given".
TACTICS_SOURCE_KEYS = ("formation", "team_shape", "pass_network")


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
    and pass_network_{team}.json for both home and away teams. Home/away and
    team-name resolution come from match_stats.json, so it must exist first —
    every other file is located relative to those two names.

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
            "home_team": str,
            "away_team": str,
        }

    Raises:
        FileNotFoundError: If any of the six extractors hasn't been run for
            this match yet.
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


def generate_outcome_section(context: dict, match_label: str, competition: str) -> OutcomeSection:
    """Generate the structured outcome section via the Messages API's structured-output mode.

    Uses client.messages.parse() against the OutcomeSection Pydantic schema so
    the response shape is guaranteed — not a plain completion parsed as JSON.
    The model sees all six source files and selects which stats/performers to
    surface (an editorial call); every value it emits must be copied from a
    field in that data, and source_field records which one.

    Args:
        context (dict): Output of load_match_context().
        match_label (str): e.g. "Spain vs England".
        competition (str): e.g. "UEFA Euro 2024".

    Returns:
        OutcomeSection: Parsed, schema-validated outcome section.

    Raises:
        RuntimeError: If the model declines to answer (stop_reason == "refusal").
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

    response = client.messages.parse(
        model=MODEL,
        max_tokens=4096,
        system=system,
        messages=[{"role": "user", "content": user_content}],
        output_format=OutcomeSection,
    )
    if response.stop_reason == "refusal":
        raise RuntimeError(
            "Model declined to generate the outcome section "
            f"(stop_details={response.stop_details})."
        )
    return response.parsed_output


def generate_tactics_section(context: dict, match_label: str, competition: str) -> str:
    """Generate the free-prose tactics section, constrained to a narrower data slice.

    Unlike generate_outcome_section(), this call receives only formation,
    team_shape, and pass_network for both teams (TACTICS_SOURCE_KEYS) — no
    match_stats, no substitutes, no progressive_map. The system prompt
    explicitly forbids claims not grounded in that data: no goals/cards/fouls,
    no inferred motivation, no tactical role label that isn't a literal
    StatsBomb position string in the data (e.g. no "false 9").

    Args:
        context (dict): Output of load_match_context(). Only the keys in
            TACTICS_SOURCE_KEYS are sent to the model.
        match_label (str): e.g. "Spain vs England".
        competition (str): e.g. "UEFA Euro 2024".

    Returns:
        str: 2-4 paragraphs of free prose, no headers or bullet lists.

    Raises:
        RuntimeError: If the model declines to answer (stop_reason == "refusal").
    """
    client = _build_client()
    tactics_context = {key: context[key] for key in TACTICS_SOURCE_KEYS}

    system = (
        f"You are writing the free-prose tactical paragraph of an auto-written match "
        f"summary for {match_label} ({competition}), explaining how the outcome "
        "happened.\n\n"
        "You are given exactly three StatsBomb-derived JSON extracts, for both teams: "
        "formation (declared shape and any tactical shifts), team_shape (empirical "
        "on-ball and off-ball positioning), and pass_network (passing structure by "
        "substitution window). These are the ONLY source of truth. You have NOT been "
        "given match_stats, substitutes, event data, shot data, or any other record "
        "of what happened in the match.\n\n"
        "Write 2-4 paragraphs of free prose (no headers, no bullet lists) covering "
        "formations and any changes, shape in and out of possession, and passing "
        "structure or hubs.\n\n"
        "Every tactical claim must be directly traceable to a field in the provided "
        "JSON. Specifically:\n"
        "- Do NOT mention goals, cards, fouls, shots, or any match event — none of "
        "that data is in front of you.\n"
        "- Do NOT infer motivation, morale, fatigue, or manager intent.\n"
        "- Do NOT use a tactical role label (e.g. \"false 9\", \"inverted fullback\") "
        "unless it is a literal position string in the data.\n"
        "- If the data doesn't support a claim, leave it out rather than guessing."
    )
    user_content = (
        "Source JSON (formation, team_shape, pass_network — both teams):\n\n"
        + json.dumps(tactics_context, indent=2)
    )

    response = client.messages.create(
        model=MODEL,
        max_tokens=1500,
        system=system,
        messages=[{"role": "user", "content": user_content}],
    )
    if response.stop_reason == "refusal":
        raise RuntimeError(
            f"Model declined to generate the tactics section (stop_details={response.stop_details})."
        )
    return next(block.text for block in response.content if block.type == "text")


def generate_match_summary(match_id: int) -> dict:
    """Generate the full two-section match summary for one match.

    Loads the six extractors' JSON from data/euro-2024/{match_id}/, calls the
    model twice (structured outcome, then free-prose tactics), and assembles
    the result into the documented output shape.

    Args:
        match_id (int): StatsBomb match ID.

    Returns:
        dict: The full match_summary.json payload — see module docstring for shape.

    Raises:
        FileNotFoundError: If any of the six source extractors hasn't been run
            for this match yet.
    """
    data_dir = Path(__file__).parents[2] / "data" / "euro-2024" / str(match_id)
    context = load_match_context(match_id, data_dir)
    competition, _, match_label = fetch_match_info(match_id)

    outcome = generate_outcome_section(context, match_label, competition)
    tactics_prose = generate_tactics_section(context, match_label, competition)

    home_team = context["home_team"]
    away_team = context["away_team"]

    return {
        "outcome": outcome.model_dump(),
        "tactics": {"prose": tactics_prose},
        "metadata": {
            "match_id": match_id,
            "home_team": home_team,
            "away_team": away_team,
            "competition": competition,
            "match_label": match_label,
            "model": MODEL,
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
            },
        },
    }


def main(match_id: int | None = None, out_dir: Path | None = None) -> None:
    """Generate the match summary for a match and write the JSON contract.

    Args:
        match_id (int | None): StatsBomb match ID; defaults to Euro 2024 Final.
        out_dir (Path | None): Output directory; defaults to data/euro-2024/{match_id}/.

    Output: {out_dir}/match_summary.json
    """
    if match_id is None:
        match_id = resolve_match("UEFA Euro", "2024", "Spain", "England")
    if out_dir is None:
        out_dir = Path(__file__).parents[2] / "data" / "euro-2024" / str(match_id)
    out_dir.mkdir(parents=True, exist_ok=True)

    summary = generate_match_summary(match_id)

    out_path = out_dir / "match_summary.json"
    with open(out_path, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"Wrote match summary → {out_path}")
    print(f"  Headline: {summary['outcome']['headline']}")
    print(f"  {len(summary['outcome']['key_stats'])} key stats, "
          f"{len(summary['outcome']['standout_performers'])} standout performers")


if __name__ == "__main__":
    main()
