"""Derive deterministic tactical findings from already-extracted StatsBomb JSON.

Implements DATA-SPEC-v2 Part 2 (`ai/match_summary/DATA-SPEC-v2.md`): reads
the extractor JSON already committed in `data/euro-2024/{match_id}/`
(never raw StatsBomb events — seam rule 3) and computes a flat list of
labelled findings, each carrying a Python-rendered `claim` the tactics
model may state word for word. The model selects and orders findings; it
never computes a label, comparison or claim itself.

`derive_` prefix because this reads extractor JSON, not StatsBomb, unlike
every `extract_*` module in this package.

Join key across files is the full `player` string (`pass_network` nodes
have no `player_id`) — `_build_display_name_lookup` resolves every full
name to its `display_name` from whichever source has it, since
`substitutes.json`'s `replaced_player` is a bare full-name string with no
`display_name` alongside it.

Public API:
    derive_tactical_findings(match_id, data_dir) -> dict
    main()

JSON output shape (tactical_findings.json):
    {
      "findings": [
        {
          "id": str, "category": str, "type": str, "team": str | null,
          "window": {"index", "from_minute", "to_minute", "source", "text"} | null,
          "game_states": [str], "subject": {...} | null, "label": str | null,
          "value": number | str | obj, "claim": str | null, "evidence": {...},
          "threshold": {"constant", "value"} | null, "notability": float,
          "definitions_version": str
        }
      ],
      "suppressed": [
        {"id", "category", "type", "team", "window", "reason", "detail"}
      ],
      "metadata": {"match_id", "definitions_version", "teams"}
    }

Notable implementation decisions not pinned down word-for-word by the spec
(flagged here for review, each also commented at its own call site):

- Finding IDs need a 3-letter team code (e.g. "ESP") the source data never
  provides (team names are always the full "Spain"/"England"). `_TEAM_CODES`
  is a small static lookup, justified by "Out of scope: any match other
  than 3943043" — it does not generalize.
- `tactical_definitions.CLAIM_TEMPLATES["player_zone"]` only has a `{lane}`
  placeholder, never `{band}` — so `player_zone`'s primary `label` is the
  lane label; the band label is computed too (the spec says "same rule for
  band") but only surfaces in `evidence`, since no claim template consumes
  it yet.
- Findings with no natural window (`goal`, `substitution`, `formation_change`,
  `role_change`, `final_score`) get `window: null` and therefore
  `game_states: []` — "every state overlapping the window" has no window to
  overlap. Only windowed findings (`formation`, `game_state`, `player_zone`,
  `team_height`, `team_width`, `block_height`, `hub`, `no_hub`, `top_pair`,
  `concentration`) get a non-empty `game_states`.
- `top_pair`'s claim names whichever player made more passes in the window
  first (`{a}`), the other second (`{b}`) — the spec's template doesn't say.
- Cross-team `comparison` findings for a per-window type (`team_height`,
  `concentration`) always compare each team's **window 0** specifically
  (not matched by time) — the spec says this explicitly for `team_height`
  ("first windows only") and this module applies the same convention to
  `concentration` by analogy, since its own worked example compares each
  team's first window too.
"""

import json
import re
from pathlib import Path

from .tactical_definitions import (
    CHANGE_MIN_SHARE,
    CLAIM_TEMPLATES,
    COMPARE_MIN_POINTS,
    COMPARE_MIN_YARDS,
    DEFINITIONS_VERSION,
    DISPLAY_FORMATS,
    HALFWAY_LINE,
    HUB_SHARE,
    LANE_DISPLAY,
    MIN_ELIGIBLE_OUTFIELD,
    MIN_NODE_EVENTS,
    MIN_PAIR_COUNT,
    MIN_WINDOW_PASSES,
    MODAL_SHARE,
    band_for_x,
    display_minute,
    lane_for_y,
)

# Finding-ID team code. Static because this spec is scoped to this one match
# only (DATA-SPEC-v2 "Out of scope") — a general match would need a real
# country-code lookup, not this.
_TEAM_CODES = {"Spain": "ESP", "England": "ENG"}

_PCT = DISPLAY_FORMATS["percentage"]
_YARDS = DISPLAY_FORMATS["yards"]


def _slug(name: str) -> str:
    """Lowercase, underscore-joined, id-safe form of a name.

    Matches the slugging every extractor's `main()` already uses for
    filenames (e.g. `extract_team_shape.main`), so filenames built from a
    team name round-trip exactly.

    Args:
        name (str): Any display string (team or player name).

    Returns:
        str: Lowercase, non-alnum runs collapsed to a single underscore,
            with leading/trailing underscores stripped.
    """
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def _team_code(team: str) -> str:
    """Resolve a full team name to its finding-ID code.

    Args:
        team (str): Full team name ("Spain", "England").

    Returns:
        str: The 3-letter code from `_TEAM_CODES`, or an uppercased slug
            prefix as a fallback for an unexpected team name.
    """
    return _TEAM_CODES.get(team, _slug(team).upper()[:3])


def _chrono_key(minute: int | None, period: int | None) -> tuple[float, float]:
    """A sortable/comparable key for a (minute, period) instant.

    `minute` alone cannot order events across periods (period 1's own
    stoppage time and period 2's early minutes both land near 45) — see
    `tactical_definitions.display_minute`. Ordering by (period, minute)
    instead is always correct, since every period-1 instant precedes every
    period-2 instant regardless of its raw minute value. `minute=None`
    (the open-ended end of a window) sorts after everything.

    Args:
        minute (int | None): Match minute, or None for "runs to full time".
        period (int | None): Match period, paired with minute.

    Returns:
        tuple[float, float]: Comparable key.
    """
    if minute is None:
        return (float("inf"), float("inf"))
    return (float(period), float(minute))


def _boundary_text(minute: int | None, period: int | None, *, is_first: bool, is_last: bool) -> str:
    """Render one edge of a window as prose, per "Window text" in DATA-SPEC-v2.

    Args:
        minute (int | None): Boundary minute, or None (only valid with is_last).
        period (int | None): Boundary period, paired with minute.
        is_first (bool): True if this is the first boundary of the match
            for this windowing (renders "kick-off").
        is_last (bool): True if this is the last boundary of the match for
            this windowing (renders "full time"), regardless of whether a
            concrete minute is also available.

    Returns:
        str: "kick-off", "full time", or `display_minute(minute, period)`.
    """
    if is_first:
        return "kick-off"
    if is_last:
        return "full time"
    return display_minute(minute, period)


def _window(
    index: int,
    from_minute: int | None,
    from_period: int | None,
    to_minute: int | None,
    to_period: int | None,
    source: str,
    *,
    is_first: bool,
    is_last: bool,
) -> dict:
    """Build a finding's `window` object.

    Args:
        index (int): Window index within its own windowing scheme.
        from_minute, from_period (int | None): Window start.
        to_minute, to_period (int | None): Window end (None if open-ended —
            only valid when is_last).
        source (str): Which windowing this is (e.g. "on_ball_period").
        is_first (bool): True if this is the match's first window of this kind.
        is_last (bool): True if this is the match's last window of this kind.

    Returns:
        dict: {"index", "from_minute", "to_minute", "source", "text"}.
    """
    from_text = _boundary_text(from_minute, from_period, is_first=is_first, is_last=False)
    to_text = _boundary_text(to_minute, to_period, is_first=False, is_last=is_last)
    return {
        "index": index,
        "from_minute": from_minute,
        "to_minute": to_minute,
        "source": source,
        "text": f"{from_text} to {to_text}",
    }


def _overlaps(
    a_from_minute, a_from_period, a_to_minute, a_to_period,
    b_from_minute, b_from_period, b_to_minute, b_to_period,
) -> bool:
    """Whether two half-open [from, to) windows overlap, period-aware.

    Returns:
        bool: True if the windows share any instant.
    """
    a_from = _chrono_key(a_from_minute, a_from_period)
    a_to = _chrono_key(a_to_minute, a_to_period)
    b_from = _chrono_key(b_from_minute, b_from_period)
    b_to = _chrono_key(b_to_minute, b_to_period)
    return a_from < b_to and b_from < a_to


def _finding(
    *, id, category, type, team, window, game_states, subject, label, value,
    claim, evidence, threshold, notability,
) -> dict:
    """Assemble one finding dict, field order as DATA-SPEC-v2's schema table.

    Returns:
        dict: The finding, with `definitions_version` filled in.
    """
    return {
        "id": id, "category": category, "type": type, "team": team,
        "window": window, "game_states": game_states, "subject": subject,
        "label": label, "value": value, "claim": claim, "evidence": evidence,
        "threshold": threshold, "notability": notability,
        "definitions_version": DEFINITIONS_VERSION,
    }


def _suppressed(*, id, category, type, team, window, reason, detail) -> dict:
    """Assemble one `suppressed` entry — a finding that was not emitted.

    Returns:
        dict: {"id", "category", "type", "team", "window", "reason", "detail"}.
    """
    return {
        "id": id, "category": category, "type": type, "team": team,
        "window": window, "reason": reason, "detail": detail,
    }


# ---------------------------------------------------------------------------
# Cross-file lookups
# ---------------------------------------------------------------------------

def _build_display_name_lookup(formation: dict, team_shape: dict, pass_network: dict, substitutes: dict) -> dict:
    """Map every full `player` name seen in any source file to its `display_name`.

    `substitutes.json`'s `replaced_player` field is a bare full-name string
    with no accompanying `display_name` — this lookup, built from every
    other source that pairs the two, is how the `substitution` claim still
    gets a real display name for the outgoing player.

    Args:
        formation (dict): team -> that team's parsed formation_*.json.
        team_shape (dict): team -> that team's parsed team_shape_*.json.
        pass_network (dict): team -> that team's parsed pass_network_*.json.
        substitutes (dict): Parsed substitutes.json.

    Returns:
        dict[str, str]: Full name -> display name.
    """
    lookup: dict[str, str] = {}
    for team_data in formation.values():
        for period in team_data["periods"]:
            for p in period["players"]:
                lookup[p["player"]] = p["display_name"]
    for team_data in team_shape.values():
        for period in team_data["on_ball"]["periods"]:
            for node in period["nodes"]:
                lookup[node["player"]] = node["display_name"]
    for team_data in pass_network.values():
        for window in team_data["windows"]:
            for node in window["nodes"]:
                lookup[node["player"]] = node["display_name"]
    for players in substitutes["teams"].values():
        for p in players:
            lookup[p["player"]] = p["display_name"]
    return lookup


def _keeper_player_ids(formation_team_data: dict) -> set:
    """Every player_id who ever appears with position "Goalkeeper" for a team.

    Args:
        formation_team_data (dict): One team's parsed formation_*.json.

    Returns:
        set[int]: Goalkeeper player_ids, for excluding them from team_height/
            team_width's "eligible outfield nodes".
    """
    ids = set()
    for period in formation_team_data["periods"]:
        for p in period["players"]:
            if p["position"] == "Goalkeeper":
                ids.add(p["player_id"])
    return ids


def _position_side(position: str) -> str:
    """Classify a StatsBomb position label's side of the pitch.

    Checked in this order because "Right Center Back"/"Left Center Back"
    contain "Center" too, but the Right/Left qualifier is the real side.

    Args:
        position (str): StatsBomb position label.

    Returns:
        str: "left", "right", or "centre".
    """
    if "Right" in position:
        return "right"
    if "Left" in position:
        return "left"
    return "centre"


def _lane_side(lane_label: str) -> str:
    """Classify a lane label's side of the pitch, for player_zone notability.

    Args:
        lane_label (str): A key of `tactical_definitions.LANE_EDGES`.

    Returns:
        str: "left", "right", or "centre".
    """
    if lane_label in ("left_wing", "left_half_space"):
        return "left"
    if lane_label in ("right_wing", "right_half_space"):
        return "right"
    return "centre"


# ---------------------------------------------------------------------------
# Game-state timeline (shared by `game_state` findings and every other
# windowed finding's `game_states` field)
# ---------------------------------------------------------------------------

def _game_state_segments(goals: list[dict], home_team: str, away_team: str) -> list[dict]:
    """Build the match's score-segment timeline from goals, kick-off to full time.

    Args:
        goals (list[dict]): shots.json entries with is_goal True, any order.
        home_team, away_team (str): Full team names.

    Returns:
        list[dict]: Ordered segments, each {index, from_minute, from_period,
            to_minute, to_period, home_score, away_score} — the score during
            that segment (before any goal that ends it). The last segment's
            to_minute/to_period are None (runs to full time).
    """
    ordered = sorted(goals, key=lambda g: _chrono_key(g["minute"], g["period"]))
    boundaries = [(0, 1)] + [(g["minute"], g["period"]) for g in ordered] + [(None, None)]

    segments = []
    home_score = away_score = 0
    for i in range(len(boundaries) - 1):
        from_minute, from_period = boundaries[i]
        to_minute, to_period = boundaries[i + 1]
        segments.append({
            "index": i,
            "from_minute": from_minute, "from_period": from_period,
            "to_minute": to_minute, "to_period": to_period,
            "home_score": home_score, "away_score": away_score,
        })
        if i < len(ordered):
            goal = ordered[i]
            if goal["team"] == home_team:
                home_score += 1
            else:
                away_score += 1
    return segments


def _game_states_for_window(
    segments: list[dict], team: str, home_team: str,
    from_minute, from_period, to_minute, to_period,
) -> list[str]:
    """Every segment label overlapping a window, from one team's side.

    Args:
        segments (list[dict]): From `_game_state_segments`.
        team (str): The team whose side "leading"/"trailing" is relative to.
        home_team (str): Full home team name, to resolve each segment's
            home_score/away_score into this team's perspective.
        from_minute, from_period, to_minute, to_period: The window's bounds.

    Returns:
        list[str]: Distinct labels ("level", "leading", "trailing") in the
            order their segments occur, for every segment overlapping the
            window.
    """
    labels = []
    for seg in segments:
        if not _overlaps(
            from_minute, from_period, to_minute, to_period,
            seg["from_minute"], seg["from_period"], seg["to_minute"], seg["to_period"],
        ):
            continue
        if seg["home_score"] == seg["away_score"]:
            label = "level"
        else:
            team_is_leading = (seg["home_score"] > seg["away_score"]) == (team == home_team)
            label = "leading" if team_is_leading else "trailing"
        if label not in labels:
            labels.append(label)
    return labels


# ---------------------------------------------------------------------------
# Context
# ---------------------------------------------------------------------------

def _context_findings(match_stats: dict, shots: list[dict], home_team: str, away_team: str) -> tuple[list[dict], list[dict], list[dict]]:
    """Build `final_score`, `goal` and `game_state` findings.

    Args:
        match_stats (dict): Parsed match_stats.json.
        shots (list[dict]): Parsed shots.json.
        home_team, away_team (str): Full team names.

    Returns:
        tuple[list[dict], list[dict], list[dict]]: (findings, suppressed,
            game_state_segments) — the segments are returned for every other
            category's `game_states` computation.
    """
    findings: list[dict] = []
    home_score = match_stats["home"]["score"]
    away_score = match_stats["away"]["score"]

    if home_score == away_score:
        claim = CLAIM_TEMPLATES["final_score"]["draw"].format(
            home=home_team, away=away_team, h=home_score, a=away_score,
        )
    else:
        winner, w = (home_team, home_score) if home_score > away_score else (away_team, away_score)
        loser, l = (away_team, away_score) if home_score > away_score else (home_team, home_score)
        claim = CLAIM_TEMPLATES["final_score"]["win"].format(winner=winner, loser=loser, w=w, l=l)

    findings.append(_finding(
        id="context.final_score", category="context", type="final_score", team=None,
        window=None, game_states=[], subject=None, label=None,
        value={"home_score": home_score, "away_score": away_score}, claim=claim,
        evidence={
            "home_team": home_team, "home_score": home_score,
            "away_team": away_team, "away_score": away_score,
            "source": "match_stats.json#home.score,away.score",
        },
        threshold=None, notability=1.0,
    ))

    goals = [s for s in shots if s["is_goal"]]
    for g in goals:
        dm = display_minute(g["minute"], g["period"])
        claim = CLAIM_TEMPLATES["goal"].format(player=g["display_name"], team=g["team"], display_minute=dm)
        findings.append(_finding(
            id=f"context.goal.{_team_code(g['team'])}.{_slug(g['display_name'])}",
            category="context", type="goal", team=g["team"], window=None, game_states=[],
            subject={"display_name": g["display_name"]}, label=None, value=g["display_name"], claim=claim,
            evidence={"minute": g["minute"], "period": g["period"], "display_minute": dm, "source": "shots.json"},
            threshold=None, notability=3.0,
        ))

    segments = _game_state_segments(goals, home_team, away_team)
    for seg in segments:
        is_first = seg["index"] == 0
        is_last = seg["index"] == len(segments) - 1
        window = _window(
            seg["index"], seg["from_minute"], seg["from_period"], seg["to_minute"], seg["to_period"],
            "game_state_segment", is_first=is_first, is_last=is_last,
        )
        from_text, to_text = window["text"].split(" to ")

        if seg["home_score"] == seg["away_score"]:
            team = None
            label = "level"
            claim = CLAIM_TEMPLATES["game_state"]["level"].format(
                score=f"{seg['home_score']}-{seg['away_score']}", **{"from": from_text}, to=to_text,
            )
            game_states = ["level"]
        else:
            team, score = (
                (home_team, f"{seg['home_score']}-{seg['away_score']}")
                if seg["home_score"] > seg["away_score"]
                else (away_team, f"{seg['away_score']}-{seg['home_score']}")
            )
            label = "leading"
            claim = CLAIM_TEMPLATES["game_state"]["leading"].format(
                team=team, score=score, **{"from": from_text}, to=to_text,
            )
            game_states = ["leading"]

        findings.append(_finding(
            id=f"context.game_state.{_team_code(team) if team else 'level'}.s{seg['index']}",
            category="context", type="game_state", team=team, window=window, game_states=game_states,
            subject=None, label=label, value=f"{seg['home_score']}-{seg['away_score']}", claim=claim,
            evidence={
                "from_minute": seg["from_minute"], "from_period": seg["from_period"],
                "to_minute": seg["to_minute"], "to_period": seg["to_period"],
                "home_score": seg["home_score"], "away_score": seg["away_score"],
                "source": "derived from shots.json goals + match_stats.json final score",
            },
            threshold=None, notability=1.0,
        ))

    return findings, [], segments


# ---------------------------------------------------------------------------
# Structure
# ---------------------------------------------------------------------------

def _structure_findings(
    formation: dict, substitutes: dict, display_name_lookup: dict,
    segments: list[dict], home_team: str,
) -> tuple[list[dict], list[dict]]:
    """Build `formation`, `formation_change`, `substitution` and `role_change` findings.

    Args:
        formation (dict): team -> parsed formation_*.json.
        substitutes (dict): Parsed substitutes.json.
        display_name_lookup (dict): From `_build_display_name_lookup`.
        segments (list[dict]): From `_game_state_segments`.
        home_team (str): Full home team name.

    Returns:
        tuple[list[dict], list[dict]]: (findings, suppressed).
    """
    findings: list[dict] = []

    for team, team_data in formation.items():
        periods = team_data["periods"]
        code = _team_code(team)

        for i, p in enumerate(periods):
            is_first, is_last = i == 0, i == len(periods) - 1
            window = _window(
                i, p["from_minute"], p["from_period"], p["to_minute"], p["to_period"],
                "formation_period", is_first=is_first, is_last=is_last,
            )
            from_text, to_text = window["text"].split(" to ")
            claim = CLAIM_TEMPLATES["formation"].format(team=team, formation=p["formation"], **{"from": from_text}, to=to_text)
            game_states = _game_states_for_window(
                segments, team, home_team, p["from_minute"], p["from_period"], p["to_minute"], p["to_period"],
            )
            findings.append(_finding(
                id=f"structure.formation.{code}.p{i}", category="structure", type="formation", team=team,
                window=window, game_states=game_states, subject=None, label=None, value=p["formation"], claim=claim,
                evidence={
                    "from_minute": p["from_minute"], "from_period": p["from_period"],
                    "to_minute": p["to_minute"], "to_period": p["to_period"],
                    "source": f"formation_{_slug(team)}.json",
                },
                threshold=None, notability=1.0,
            ))

            if i > 0 and periods[i - 1]["formation"] != p["formation"]:
                dm = display_minute(p["from_minute"], p["from_period"])
                claim = CLAIM_TEMPLATES["formation_change"].format(
                    team=team, old=periods[i - 1]["formation"], new=p["formation"], display_minute=dm,
                )
                findings.append(_finding(
                    id=f"structure.formation_change.{code}.p{i}", category="structure", type="formation_change",
                    team=team, window=None, game_states=[], subject=None,
                    label=None, value={"old": periods[i - 1]["formation"], "new": p["formation"]}, claim=claim,
                    evidence={
                        "minute": p["from_minute"], "period": p["from_period"], "display_minute": dm,
                        "source": f"formation_{_slug(team)}.json",
                    },
                    threshold=None, notability=3.0,
                ))

            # role_change: same player_id in this period and the previous one,
            # with a different declared position.
            if i > 0:
                prev_by_id = {pl["player_id"]: pl for pl in periods[i - 1]["players"]}
                for pl in p["players"]:
                    prev = prev_by_id.get(pl["player_id"])
                    if prev is not None and prev["position"] != pl["position"]:
                        dm = display_minute(p["from_minute"], p["from_period"])
                        claim = CLAIM_TEMPLATES["role_change"].format(
                            player=pl["display_name"], old_position=prev["position"],
                            new_position=pl["position"], display_minute=dm,
                        )
                        findings.append(_finding(
                            id=f"structure.role_change.{code}.{_slug(pl['display_name'])}.p{i}",
                            category="structure", type="role_change", team=team, window=None, game_states=[],
                            subject={"player": pl["player"], "display_name": pl["display_name"]}, label=None,
                            value={"old_position": prev["position"], "new_position": pl["position"]}, claim=claim,
                            evidence={
                                "minute": p["from_minute"], "period": p["from_period"], "display_minute": dm,
                                "source": f"formation_{_slug(team)}.json",
                            },
                            threshold=None, notability=2.0,
                        ))

    for team, players in substitutes["teams"].items():
        code = _team_code(team)
        for sub in players:
            off_display = display_name_lookup.get(sub["replaced_player"], sub["replaced_player"])
            dm = display_minute(sub["on_minute"], sub["on_period"])
            claim = CLAIM_TEMPLATES["substitution"].format(on=sub["display_name"], off=off_display, team=team, display_minute=dm)
            findings.append(_finding(
                id=f"structure.substitution.{code}.{_slug(sub['display_name'])}", category="structure",
                type="substitution", team=team, window=None, game_states=[],
                subject={"player": sub["player"], "display_name": sub["display_name"]}, label=None,
                value={"on": sub["display_name"], "off": off_display}, claim=claim,
                evidence={
                    "minute": sub["on_minute"], "period": sub["on_period"], "display_minute": dm,
                    "on_player": sub["player"], "off_player": sub["replaced_player"],
                    "source": "substitutes.json",
                },
                threshold=None, notability=1.0,
            ))

    return findings, []


# ---------------------------------------------------------------------------
# Shape in possession
# ---------------------------------------------------------------------------

def _declared_side(formation_team_data: dict, player_id: int, from_minute, from_period, to_minute, to_period) -> str | None:
    """A player's declared-position side during a window, for player_zone notability.

    Args:
        formation_team_data (dict): The team's parsed formation_*.json.
        player_id (int): StatsBomb player_id.
        from_minute, from_period, to_minute, to_period: The on-ball window's bounds.

    Returns:
        str | None: "left"/"right"/"centre" from whichever formation period
            overlaps the window and lists this player, or None if no such
            period is found (conservative — no notability boost applied).
    """
    for p in formation_team_data["periods"]:
        if not _overlaps(from_minute, from_period, to_minute, to_period, p["from_minute"], p["from_period"], p["to_minute"], p["to_period"]):
            continue
        for pl in p["players"]:
            if pl["player_id"] == player_id:
                return _position_side(pl["position"])
    return None


def _modal_label(counts: dict, total: int) -> tuple[str, bool, list[tuple[str, int]]]:
    """Modal-share labelling shared by player_zone's lane and band computation.

    Args:
        counts (dict[str, int]): Per-bucket touch counts.
        total (int): Sum of counts (== event_count).

    Returns:
        tuple[str, bool, list[tuple[str, int]]]: (label, is_mixed, top_two)
            where label is the modal bucket name or "mixed", and top_two is
            the two highest (bucket, count) pairs, highest first.
    """
    ranked = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
    top_bucket, top_count = ranked[0]
    if top_count / total >= MODAL_SHARE:
        return top_bucket, False, ranked[:2]
    return "mixed", True, ranked[:2]


def _in_possession_findings(team_shape: dict, formation: dict, segments: list[dict], home_team: str) -> tuple[list[dict], list[dict]]:
    """Build `player_zone`, `team_height` and `team_width` findings.

    Args:
        team_shape (dict): team -> parsed team_shape_*.json.
        formation (dict): team -> parsed formation_*.json.
        segments (list[dict]): From `_game_state_segments`.
        home_team (str): Full home team name.

    Returns:
        tuple[list[dict], list[dict]]: (findings, suppressed).
    """
    findings: list[dict] = []
    suppressed: list[dict] = []

    for team, team_data in team_shape.items():
        code = _team_code(team)
        keeper_ids = _keeper_player_ids(formation[team])
        periods = team_data["on_ball"]["periods"]

        for i, p in enumerate(periods):
            is_first, is_last = i == 0, i == len(periods) - 1
            window = _window(
                i, p["from_minute"], p["from_period"], p["to_minute"], p["to_period"],
                "on_ball_period", is_first=is_first, is_last=is_last,
            )
            game_states = _game_states_for_window(
                segments, team, home_team, p["from_minute"], p["from_period"], p["to_minute"], p["to_period"],
            )

            for node in p["nodes"]:
                event_count = node["event_count"]
                if event_count < MIN_NODE_EVENTS:
                    suppressed.append(_suppressed(
                        id=f"in_possession.player_zone.{code}.w{i}.{_slug(node['display_name'])}",
                        category="in_possession", type="player_zone", team=team, window=window,
                        reason="MIN_NODE_EVENTS", detail={"event_count": event_count, "required": MIN_NODE_EVENTS},
                    ))
                    continue

                lane_label, lane_mixed, lane_top2 = _modal_label(node["lane_counts"], event_count)
                band_label, band_mixed, band_top2 = _modal_label(node["band_counts"], event_count)

                if lane_mixed:
                    (l1, n1), (l2, n2) = lane_top2
                    claim = CLAIM_TEMPLATES["player_zone"]["mixed"].format(
                        player=node["display_name"], lane1=LANE_DISPLAY[l1], n1=n1,
                        lane2=LANE_DISPLAY[l2], n2=n2, window=window["text"],
                    )
                else:
                    claim = CLAIM_TEMPLATES["player_zone"]["lane"].format(
                        player=node["display_name"], n=lane_top2[0][1], total=event_count,
                        lane=LANE_DISPLAY[lane_label], window=window["text"],
                    )

                declared_side = (
                    None if node["player_id"] in keeper_ids
                    else _declared_side(formation[team], node["player_id"], p["from_minute"], p["from_period"], p["to_minute"], p["to_period"])
                )
                observed_side = _lane_side(lane_top2[0][0] if lane_mixed else lane_label)
                notability = 1.5 if (declared_side is not None and declared_side != observed_side) else 1.0

                findings.append(_finding(
                    id=f"in_possession.player_zone.{code}.w{i}.{_slug(node['display_name'])}",
                    category="in_possession", type="player_zone", team=team, window=window, game_states=game_states,
                    subject={"player": node["player"], "display_name": node["display_name"]},
                    label=lane_label, value=lane_label, claim=claim,
                    evidence={
                        "event_count": event_count, "lane_counts": node["lane_counts"], "band_counts": node["band_counts"],
                        "band_label": band_label, "band_mixed": band_mixed,
                        "declared_side": declared_side, "observed_side": observed_side,
                        "source": f"team_shape_{_slug(team)}.json#on_ball",
                    },
                    threshold={"constant": "MODAL_SHARE", "value": MODAL_SHARE}, notability=notability,
                ))

            outfield = [n for n in p["nodes"] if n["player_id"] not in keeper_ids and n["event_count"] >= MIN_NODE_EVENTS]
            if len(outfield) < MIN_ELIGIBLE_OUTFIELD:
                detail = {"eligible_outfield_count": len(outfield), "required": MIN_ELIGIBLE_OUTFIELD}
                suppressed.append(_suppressed(
                    id=f"in_possession.team_height.{code}.w{i}", category="in_possession", type="team_height",
                    team=team, window=window, reason="MIN_ELIGIBLE_OUTFIELD", detail=detail,
                ))
                suppressed.append(_suppressed(
                    id=f"in_possession.team_width.{code}.w{i}", category="in_possession", type="team_width",
                    team=team, window=window, reason="MIN_ELIGIBLE_OUTFIELD", detail=detail,
                ))
                continue

            total_events = sum(n["event_count"] for n in outfield)
            mean_x = sum(n["x"] * n["event_count"] for n in outfield) / total_events
            label = "own_half" if mean_x < HALFWAY_LINE else "opposition_half"
            claim = CLAIM_TEMPLATES["team_height"][label].format(team=team, window=window["text"])
            findings.append(_finding(
                id=f"in_possession.team_height.{code}.w{i}", category="in_possession", type="team_height",
                team=team, window=window, game_states=game_states, subject=None, label=label,
                value=round(mean_x, 2), claim=claim,
                evidence={
                    "mean_x": round(mean_x, 2), "eligible_outfield_count": len(outfield), "event_count_total": total_events,
                    "source": f"team_shape_{_slug(team)}.json#on_ball",
                },
                threshold={"constant": "HALFWAY_LINE", "value": HALFWAY_LINE}, notability=1.0,
            ))

            ys = [n["y"] for n in outfield]
            width = max(ys) - min(ys)
            findings.append(_finding(
                id=f"in_possession.team_width.{code}.w{i}", category="in_possession", type="team_width",
                team=team, window=window, game_states=game_states, subject=None, label=None,
                value=round(width, 2), claim=None,
                evidence={"width": round(width, 2), "eligible_outfield_count": len(outfield), "source": f"team_shape_{_slug(team)}.json#on_ball"},
                threshold=None, notability=1.0,
            ))

    return findings, suppressed


# ---------------------------------------------------------------------------
# Shape out of possession
# ---------------------------------------------------------------------------

def _out_of_possession_findings(team_shape: dict, segments: list[dict], home_team: str) -> tuple[list[dict], list[dict]]:
    """Build `block_height` findings.

    Args:
        team_shape (dict): team -> parsed team_shape_*.json.
        segments (list[dict]): From `_game_state_segments`.
        home_team (str): Full home team name.

    Returns:
        tuple[list[dict], list[dict]]: (findings, []) — block_height is never suppressed.
    """
    findings = []
    for team, team_data in team_shape.items():
        off_ball = team_data["off_ball"]
        window = _window(0, 0, 1, None, None, "whole_match", is_first=True, is_last=True)
        game_states = _game_states_for_window(segments, team, home_team, 0, 1, None, None)
        findings.append(_finding(
            id=f"out_of_possession.block_height.{_team_code(team)}.whole_match", category="out_of_possession",
            type="block_height", team=team, window=window, game_states=game_states, subject=None, label=None,
            value=off_ball["centroid"]["x"], claim=None,
            evidence={
                "centroid_x": off_ball["centroid"]["x"], "camera_caveat": team_data["metadata"]["camera_caveat"],
                "source": f"team_shape_{_slug(team)}.json#off_ball.centroid",
            },
            threshold=None, notability=1.0,
        ))
    return findings, []


# ---------------------------------------------------------------------------
# Passing structure
# ---------------------------------------------------------------------------

def _passing_findings(pass_network: dict, segments: list[dict], home_team: str) -> tuple[list[dict], list[dict]]:
    """Build `hub`, `no_hub`, `top_pair` and `concentration` findings.

    Args:
        pass_network (dict): team -> parsed pass_network_*.json.
        segments (list[dict]): From `_game_state_segments`.
        home_team (str): Full home team name.

    Returns:
        tuple[list[dict], list[dict]]: (findings, suppressed).
    """
    findings: list[dict] = []
    suppressed: list[dict] = []

    for team, team_data in pass_network.items():
        code = _team_code(team)
        windows = team_data["windows"]

        for w in windows:
            i = w["index"]
            is_first, is_last = i == 0, i == len(windows) - 1
            window = _window(i, w["from_minute"], w["from_period"], w["to_minute"], w["to_period"], "pass_network_window", is_first=is_first, is_last=is_last)
            game_states = _game_states_for_window(segments, team, home_team, w["from_minute"], w["from_period"], w["to_minute"], w["to_period"])

            window_passes = sum(n["passes"] for n in w["nodes"])
            if window_passes < MIN_WINDOW_PASSES:
                for finding_type in ("hub", "no_hub", "top_pair", "concentration"):
                    suppressed.append(_suppressed(
                        id=f"passing.{finding_type}.{code}.w{i}", category="passing", type=finding_type,
                        team=team, window=window, reason="MIN_WINDOW_PASSES",
                        detail={"window_passes": window_passes, "required": MIN_WINDOW_PASSES},
                    ))
                continue

            received: dict[str, int] = {}
            for e in w["edges"]:
                received[e["to"]] = received.get(e["to"], 0) + e["count"]

            shares: dict[str, float] = {}
            for n in w["nodes"]:
                made = n["passes"]
                recv = received.get(n["player"], 0)
                shares[n["player"]] = (made + recv) / (2 * window_passes)

            hubs = [n for n in w["nodes"] if shares[n["player"]] >= HUB_SHARE]
            for n in hubs:
                share = shares[n["player"]]
                claim = CLAIM_TEMPLATES["hub"].format(player=n["display_name"], team=team, share=_PCT(share * 100), window=window["text"])
                findings.append(_finding(
                    id=f"passing.hub.{code}.w{i}.{_slug(n['display_name'])}", category="passing", type="hub",
                    team=team, window=window, game_states=game_states,
                    subject={"player": n["player"], "display_name": n["display_name"]}, label=None,
                    value=round(share, 4), claim=claim,
                    evidence={"passes_made": n["passes"], "passes_received": received.get(n["player"], 0), "share": round(share, 4), "source": f"pass_network_{team}.json"},
                    threshold={"constant": "HUB_SHARE", "value": HUB_SHARE}, notability=share / HUB_SHARE,
                ))

            if not hubs:
                most = max(w["nodes"], key=lambda n: shares[n["player"]])
                share = shares[most["player"]]
                claim = CLAIM_TEMPLATES["no_hub"].format(team=team, player=most["display_name"], share=_PCT(share * 100), window=window["text"])
                findings.append(_finding(
                    id=f"passing.no_hub.{code}.w{i}", category="passing", type="no_hub", team=team,
                    window=window, game_states=game_states, subject=None, label=None, value=round(share, 4), claim=claim,
                    evidence={"most_involved_player": most["display_name"], "share": round(share, 4), "source": f"pass_network_{team}.json"},
                    threshold={"constant": "HUB_SHARE", "value": HUB_SHARE}, notability=1.0,
                ))

            pair_totals: dict[frozenset, int] = {}
            for e in w["edges"]:
                key = frozenset({e["from"], e["to"]})
                pair_totals[key] = pair_totals.get(key, 0) + e["count"]
            qualifying = {k: v for k, v in pair_totals.items() if v >= MIN_PAIR_COUNT}
            ranked_totals = sorted(set(qualifying.values()), reverse=True)
            cutoff = ranked_totals[2] if len(ranked_totals) >= 3 else (ranked_totals[-1] if ranked_totals else None)
            display_by_player = {n["player"]: n["display_name"] for n in w["nodes"]}
            passes_made_by_player = {n["player"]: n["passes"] for n in w["nodes"]}
            if cutoff is not None:
                for pair, total in sorted(qualifying.items(), key=lambda kv: -kv[1]):
                    if total < cutoff:
                        continue
                    # Full name as a secondary key: `pair` is a frozenset, whose
                    # iteration order for tied passes_made would otherwise depend
                    # on PYTHONHASHSEED and vary nondeterministically run to run.
                    p1, p2 = sorted(pair, key=lambda p: (-passes_made_by_player.get(p, 0), p))
                    a, b = display_by_player.get(p1, p1), display_by_player.get(p2, p2)
                    claim = CLAIM_TEMPLATES["top_pair"].format(a=a, b=b, n=total, window=window["text"])
                    findings.append(_finding(
                        id=f"passing.top_pair.{code}.w{i}.{_slug(a)}_{_slug(b)}", category="passing", type="top_pair",
                        team=team, window=window, game_states=game_states, subject={"pair": [a, b]}, label=None,
                        value=total, claim=claim,
                        evidence={"bidirectional_total": total, "source": f"pass_network_{team}.json"},
                        threshold={"constant": "MIN_PAIR_COUNT", "value": MIN_PAIR_COUNT},
                        notability=total / window_passes / 0.05,
                    ))

            top3 = sorted(shares.values(), reverse=True)[:3]
            concentration = sum(top3)
            findings.append(_finding(
                id=f"passing.concentration.{code}.w{i}", category="passing", type="concentration", team=team,
                window=window, game_states=game_states, subject=None, label=None, value=round(concentration, 4), claim=None,
                evidence={"top3_share": round(concentration, 4), "window_passes": window_passes, "source": f"pass_network_{team}.json"},
                threshold=None, notability=1.0,
            ))

    return findings, suppressed


# ---------------------------------------------------------------------------
# Cross-cutting: comparison, change
# ---------------------------------------------------------------------------

def _cross_cutting_findings(findings: list[dict], home_team: str, away_team: str) -> tuple[list[dict], list[dict]]:
    """Build `comparison` and `change` findings from the findings already built.

    Args:
        findings (list[dict]): Every finding from the five base categories.
        home_team, away_team (str): Full team names.

    Returns:
        tuple[list[dict], list[dict]]: (findings, suppressed).
    """
    out: list[dict] = []
    suppressed: list[dict] = []

    by_type_team: dict[tuple, list[dict]] = {}
    for f in findings:
        by_type_team.setdefault((f["type"], f["team"]), []).append(f)

    def first_window(finding_type, team):
        rows = [f for f in by_type_team.get((finding_type, team), []) if f["window"] is not None]
        rows.sort(key=lambda f: f["window"]["index"])
        return rows[0] if rows else None

    # block_height — whole match, both teams always have exactly one.
    home_bh = first_window("block_height", home_team)
    away_bh = first_window("block_height", away_team)
    if home_bh and away_bh:
        gap = abs(home_bh["value"] - away_bh["value"])
        deeper, other = (home_team, away_team) if home_bh["value"] < away_bh["value"] else (away_team, home_team)
        if gap >= COMPARE_MIN_YARDS:
            claim = CLAIM_TEMPLATES["comparison"]["block_height"].format(deeper=deeper, gap=_YARDS(gap), other=other)
            out.append(_finding(
                id=f"cross.comparison.block_height.{_team_code(deeper)}", category="cross_cutting", type="comparison",
                team=deeper, window=None, game_states=[], subject=None, label="deeper", value=round(gap, 2), claim=claim,
                evidence={"deeper_x": min(home_bh["value"], away_bh["value"]), "other_x": max(home_bh["value"], away_bh["value"]), "gap": round(gap, 2)},
                threshold={"constant": "COMPARE_MIN_YARDS", "value": COMPARE_MIN_YARDS}, notability=gap / COMPARE_MIN_YARDS,
            ))
        else:
            suppressed.append(_suppressed(
                id="cross.comparison.block_height", category="cross_cutting", type="comparison", team=None,
                window=None, reason="COMPARE_MIN_YARDS", detail={"gap": round(gap, 2), "required": COMPARE_MIN_YARDS},
            ))

    # team_height / concentration — each team's window 0 specifically.
    for finding_type, compare_min, display_key in (("team_height", COMPARE_MIN_YARDS, "yards"), ("concentration", COMPARE_MIN_POINTS, "points")):
        home_f = first_window(finding_type, home_team)
        away_f = first_window(finding_type, away_team)
        if not (home_f and away_f):
            continue
        gap = abs(home_f["value"] - away_f["value"])
        # concentration's value is a fraction (0.448), but COMPARE_MIN_POINTS
        # is in percentage points (5, meaning 5.0) — scale before comparing.
        gap_scaled = gap * 100 if display_key == "points" else gap
        higher_f, other_f = (home_f, away_f) if home_f["value"] > away_f["value"] else (away_f, home_f)
        if gap_scaled < compare_min:
            suppressed.append(_suppressed(
                id=f"cross.comparison.{finding_type}", category="cross_cutting", type="comparison", team=None,
                window=None, reason="COMPARE_MIN_YARDS" if display_key == "yards" else "COMPARE_MIN_POINTS",
                detail={"gap": round(gap_scaled, 2), "required": compare_min},
            ))
            continue
        if finding_type == "team_height":
            claim = CLAIM_TEMPLATES["comparison"]["team_height"].format(
                higher=higher_f["team"], gap=_YARDS(gap), other=other_f["team"],
                window_a=higher_f["window"]["text"], window_b=other_f["window"]["text"],
            )
            label = "higher"
        else:
            claim = CLAIM_TEMPLATES["comparison"]["concentration"].format(
                team=higher_f["team"], other=other_f["team"], a=_PCT(higher_f["value"] * 100), b=_PCT(other_f["value"] * 100),
                window=higher_f["window"]["text"],
            )
            label = "more_concentrated"
        out.append(_finding(
            id=f"cross.comparison.{finding_type}.{_team_code(higher_f['team'])}", category="cross_cutting", type="comparison",
            team=higher_f["team"], window=None, game_states=[], subject=None, label=label, value=round(gap_scaled, 4), claim=claim,
            evidence={"higher_value": higher_f["value"], "other_value": other_f["value"], "gap": round(gap_scaled, 4)},
            threshold={"constant": "COMPARE_MIN_YARDS" if display_key == "yards" else "COMPARE_MIN_POINTS", "value": compare_min},
            notability=gap_scaled / compare_min,
        ))

    # team_width — same window-0-only pattern; this spec has no claim
    # template for it (CLAIM_TEMPLATES["comparison"] has no "team_width" key),
    # so even if emitted it would carry a label but a null claim.
    home_tw = first_window("team_width", home_team)
    away_tw = first_window("team_width", away_team)
    if home_tw and away_tw:
        gap = abs(home_tw["value"] - away_tw["value"])
        if gap < COMPARE_MIN_YARDS:
            suppressed.append(_suppressed(
                id="cross.comparison.team_width", category="cross_cutting", type="comparison", team=None,
                window=None, reason="COMPARE_MIN_YARDS", detail={"gap": round(gap, 2), "required": COMPARE_MIN_YARDS},
            ))
        else:
            wider, other = (home_team, away_team) if home_tw["value"] > away_tw["value"] else (away_team, home_team)
            out.append(_finding(
                id=f"cross.comparison.team_width.{_team_code(wider)}", category="cross_cutting", type="comparison",
                team=wider, window=None, game_states=[], subject=None, label="wider", value=round(gap, 2), claim=None,
                evidence={"gap": round(gap, 2)}, threshold={"constant": "COMPARE_MIN_YARDS", "value": COMPARE_MIN_YARDS},
                notability=gap / COMPARE_MIN_YARDS,
            ))

    # change (hub only — formation_change/role_change are already change
    # findings and are not duplicated here).
    for team in (home_team, away_team):
        hub_rows = [f for f in by_type_team.get(("hub", team), []) if f["window"] is not None]
        no_hub_rows = [f for f in by_type_team.get(("no_hub", team), []) if f["window"] is not None]
        # "Consecutive emitted windows": a passing window with no hub/no_hub
        # finding at all was suppressed by MIN_WINDOW_PASSES and isn't
        # adjacent to anything for this check. hub/no_hub findings only
        # carry a share for hubs and the single most-involved non-hub, so a
        # player who was a hub in one emitted window but isn't in the next
        # emitted window's hub rows has no comparable share there — only
        # players with a `hub` finding in both windows are checked.
        emitted_window_indices = sorted({f["window"]["index"] for f in hub_rows} | {f["window"]["index"] for f in no_hub_rows})
        for idx in range(len(emitted_window_indices) - 1):
            w_a, w_b = emitted_window_indices[idx], emitted_window_indices[idx + 1]
            shares_a = {f["subject"]["player"]: f["value"] for f in hub_rows if f["window"]["index"] == w_a}
            shares_b = {f["subject"]["player"]: f["value"] for f in hub_rows if f["window"]["index"] == w_b}
            for player, share_a in shares_a.items():
                share_b = shares_b.get(player)
                if share_b is None:
                    continue
                delta = share_b - share_a
                crosses = (share_a >= HUB_SHARE) != (share_b >= HUB_SHARE)
                if abs(delta) >= CHANGE_MIN_SHARE and crosses:
                    player_rows = [f for f in hub_rows if f["window"]["index"] in (w_a, w_b) and f["subject"]["player"] == player]
                    display_name = player_rows[0]["subject"]["display_name"]
                    window_a_text = next(f["window"]["text"] for f in hub_rows if f["window"]["index"] == w_a)
                    window_b_text = next(f["window"]["text"] for f in hub_rows if f["window"]["index"] == w_b)
                    direction = "rose" if delta > 0 else "fell"
                    claim = CLAIM_TEMPLATES["change"]["hub"].format(
                        player=display_name, direction=direction, a=_PCT(share_a * 100), b=_PCT(share_b * 100),
                        window_1=window_a_text, window_2=window_b_text,
                    )
                    out.append(_finding(
                        id=f"cross.change.hub.{_team_code(team)}.{_slug(display_name)}.w{w_a}_w{w_b}",
                        category="cross_cutting", type="change", team=team, window=None, game_states=[],
                        subject={"player": player, "display_name": display_name}, label=direction,
                        value=round(delta, 4), claim=claim,
                        evidence={"share_a": share_a, "share_b": share_b, "delta": round(delta, 4)},
                        threshold={"constant": "CHANGE_MIN_SHARE", "value": CHANGE_MIN_SHARE},
                        notability=abs(delta) / CHANGE_MIN_SHARE,
                    ))

    return out, suppressed


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def derive_tactical_findings(match_id: int, data_dir: Path | str) -> dict:
    """Compute every tactical finding for one match from its extractor JSON.

    Reads match_stats.json, shots.json, formation_{team}.json, substitutes.json,
    team_shape_{team}.json and pass_network_{Team}.json for both teams. Never
    reads raw StatsBomb data — seam rule 3.

    Args:
        match_id (int): StatsBomb match ID.
        data_dir (Path | str): Directory holding that match's extractor JSON
            (typically `data/euro-2024/{match_id}/`).

    Returns:
        dict: {"findings": [...], "suppressed": [...], "metadata": {...}}.
    """
    data_dir = Path(data_dir)

    def _load(name: str):
        with open(data_dir / name) as f:
            return json.load(f)

    match_stats = _load("match_stats.json")
    shots = _load("shots.json")
    substitutes = _load("substitutes.json")
    home_team = match_stats["home"]["team"]
    away_team = match_stats["away"]["team"]
    teams = [home_team, away_team]

    formation = {team: _load(f"formation_{_slug(team)}.json") for team in teams}
    team_shape = {team: _load(f"team_shape_{_slug(team)}.json") for team in teams}
    pass_network = {team: _load(f"pass_network_{team}.json") for team in teams}

    display_name_lookup = _build_display_name_lookup(formation, team_shape, pass_network, substitutes)

    findings: list[dict] = []
    suppressed: list[dict] = []

    context_findings, context_suppressed, segments = _context_findings(match_stats, shots, home_team, away_team)
    findings += context_findings
    suppressed += context_suppressed

    structure_findings, structure_suppressed = _structure_findings(formation, substitutes, display_name_lookup, segments, home_team)
    findings += structure_findings
    suppressed += structure_suppressed

    in_poss_findings, in_poss_suppressed = _in_possession_findings(team_shape, formation, segments, home_team)
    findings += in_poss_findings
    suppressed += in_poss_suppressed

    out_poss_findings, out_poss_suppressed = _out_of_possession_findings(team_shape, segments, home_team)
    findings += out_poss_findings
    suppressed += out_poss_suppressed

    passing_findings, passing_suppressed = _passing_findings(pass_network, segments, home_team)
    findings += passing_findings
    suppressed += passing_suppressed

    cross_findings, cross_suppressed = _cross_cutting_findings(findings, home_team, away_team)
    findings += cross_findings
    suppressed += cross_suppressed

    return {
        "findings": findings,
        "suppressed": suppressed,
        "metadata": {
            "match_id": match_id,
            "definitions_version": DEFINITIONS_VERSION,
            "teams": teams,
        },
    }


def main(match_id: int | None = None, data_dir: Path | None = None) -> None:
    """Derive tactical findings for a match and write tactical_findings.json.

    Args:
        match_id (int | None): StatsBomb match ID; defaults to 3943043
            (the only match this spec is scoped to).
        data_dir (Path | None): Directory holding (and to write) the match's
            extractor JSON; defaults to data/euro-2024/{match_id}/.

    Output: {data_dir}/tactical_findings.json
    """
    if match_id is None:
        match_id = 3943043
    if data_dir is None:
        data_dir = Path(__file__).parents[2] / "data" / "euro-2024" / str(match_id)

    payload = derive_tactical_findings(match_id, data_dir)
    out_path = Path(data_dir) / "tactical_findings.json"
    with open(out_path, "w") as f:
        json.dump(payload, f, indent=2)

    n_claims = sum(1 for finding in payload["findings"] if finding["claim"] is not None)
    print(f"{len(payload['findings'])} findings ({n_claims} with a claim), {len(payload['suppressed'])} suppressed → {out_path}")


if __name__ == "__main__":
    main()
