"""Build Euro-2024-relative tercile reference distributions (DATA-SPEC-v3's
"Tournament reference labels" section): for each tercile-labelled measure,
collect its value across every team-match, and expose a pure labelling
function other code can apply to a single match's value.

Only three measures are tercile-labelled: `ppda` (Q4), `block_height`
(Q5, v2's existing `team_shape` off-ball centroid), and
`defensive_action_height` (Q5). Values are read from the already-committed
Part 1/v2 extractor output under `data/euro-2024/{match_id}/` — this module
never reads raw StatsBomb events itself.

Tercile math: given `n` sorted-ascending values and `k = n // 3`, `cut_low`
is the value at index `k - 1` (the top of the bottom third by position) and
`cut_high` is the value at index `2*k - 1` (the top of the middle third).
Any remainder from `n` not dividing evenly by 3 is absorbed into the top
third. Labelling is direction-agnostic and "lower tercile owns the cut"
(each cut point is inclusive on its lower side, the same half-open
convention `lane_for_y`/`band_for_x` in `tactical_definitions.py` use):
`v <= cut_low` -> "bottom_third"; `cut_low < v <= cut_high` ->
"middle_third"; `v > cut_high` -> "top_third". Which third is favourable
per measure (e.g. for PPDA, low = intense = top_third) is recorded as a
`direction` string in the output, for Part 4's claim templates to consult —
this module does not branch on it.

Public API:
    tercile_cutpoints(values) -> tuple[float, float]
    tercile_label(value, cut_low, cut_high) -> str
    build_reference_distributions(match_ids, data_root) -> dict
    main()

JSON output shape (data/euro-2024/reference/reference_distributions.json):
    {
        "measures": {
            "<measure>": {
                "direction": "low_is_top_third" | "high_is_top_third",
                "n": int,
                "sorted_values": [float, ...],
                "cut_low": float,
                "cut_high": float,
                "missing": [{"match_id": int, "team": str, "reason": str}]
            }
        },
        "metadata": {
            "definitions_version": str,
            "build_date": "YYYY-MM-DD",
            "match_count": int,
            "competition": "UEFA Euro 2024"
        }
    }
Written to: data/euro-2024/reference/reference_distributions.json
"""

import json
import re
from datetime import date
from pathlib import Path

from .tactical_definitions import DEFINITIONS_VERSION

DIRECTIONS: dict[str, str] = {
    "ppda": "low_is_top_third",
    "block_height": "high_is_top_third",
    "defensive_action_height": "high_is_top_third",
}


def _team_slug(team: str) -> str:
    """Lowercase, underscore-joined, filename-safe form of a team name.

    Args:
        team (str): Team name exactly as returned by StatsBomb.

    Returns:
        str: e.g. "Spain" -> "spain".
    """
    return re.sub(r"[^a-z0-9]+", "_", team.lower()).strip("_")


def tercile_cutpoints(values: list[float]) -> tuple[float, float]:
    """Compute the two tercile cut points for a distribution.

    `k = n // 3` (floor). `cut_low` is the value at index `k - 1` (the
    maximum value of the bottom third by sorted position); `cut_high` is
    the value at index `2*k - 1` (the maximum value of the middle third).
    Any remainder from `n` not dividing evenly by 3 is absorbed into the
    top third, not spread across all three.

    Args:
        values (list[float]): At least 3 values; sorted ascending internally
            (the input need not already be sorted).

    Returns:
        tuple[float, float]: (cut_low, cut_high).

    Raises:
        ValueError: If fewer than 3 values are given.
    """
    if len(values) < 3:
        raise ValueError(f"need at least 3 values to compute terciles, got {len(values)}")
    ordered = sorted(values)
    k = len(ordered) // 3
    return ordered[k - 1], ordered[2 * k - 1]


def tercile_label(value: float, cut_low: float, cut_high: float) -> str:
    """Classify a value by its position relative to two tercile cut points.

    Direction-agnostic: this only reports where `value` sits in the sorted
    distribution, not which third is "good" for the measure it came from
    (see this module's docstring). Each cut point is inclusive on its lower
    side ("lower tercile owns the cut") — a value exactly equal to `cut_low`
    or `cut_high` belongs to the third below it, not the one above.

    Args:
        value (float): The value to classify.
        cut_low (float): Lower tercile cut point, from `tercile_cutpoints`.
        cut_high (float): Upper tercile cut point, from `tercile_cutpoints`.

    Returns:
        str: One of "bottom_third", "middle_third", "top_third".
    """
    if value <= cut_low:
        return "bottom_third"
    if value <= cut_high:
        return "middle_third"
    return "top_third"


def _read_json(path: Path) -> dict | None:
    """Read a JSON file, returning None (not raising) if it doesn't exist.

    Args:
        path (Path): File to read.

    Returns:
        dict | None: Parsed JSON, or None if the file is missing.
    """
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


def _collect_ppda(match_id: int, team: str, match_dir: Path, missing: list[dict]) -> float | None:
    """Read one team's PPDA value from that match's `pressing.json`.

    Args:
        match_id (int): StatsBomb match ID, for the `missing` report.
        team (str): Team name as it appears in StatsBomb data.
        match_dir (Path): The match's `data/euro-2024/{match_id}/` directory.
        missing (list[dict]): Appended to in place when the value can't be read.

    Returns:
        float | None: The team's PPDA value, or None if unavailable.
    """
    payload = _read_json(match_dir / "pressing.json")
    if payload is None:
        missing.append({"match_id": match_id, "team": team, "reason": "pressing.json not found"})
        return None
    value = payload.get("teams", {}).get(team, {}).get("ppda", {}).get("value")
    if value is None:
        missing.append({"match_id": match_id, "team": team, "reason": "ppda.value is null (no qualifying defensive actions)"})
        return None
    return float(value)


def _collect_defensive_action_height(match_id: int, team: str, match_dir: Path, missing: list[dict]) -> float | None:
    """Read one team's defensive action height from `defending_{team_slug}.json`.

    Args:
        match_id (int): StatsBomb match ID, for the `missing` report.
        team (str): Team name as it appears in StatsBomb data.
        match_dir (Path): The match's `data/euro-2024/{match_id}/` directory.
        missing (list[dict]): Appended to in place when the value can't be read.

    Returns:
        float | None: The team's defensive_action_height mean_x, or None.
    """
    payload = _read_json(match_dir / f"defending_{_team_slug(team)}.json")
    if payload is None:
        missing.append({"match_id": match_id, "team": team, "reason": "defending_{team}.json not found"})
        return None
    return float(payload["defensive_action_height"]["mean_x"])


def _collect_block_height(match_id: int, team: str, match_dir: Path, missing: list[dict]) -> float | None:
    """Read one team's block height (v2's off-ball centroid x) from `team_shape_{team_slug}.json`.

    Args:
        match_id (int): StatsBomb match ID, for the `missing` report.
        team (str): Team name as it appears in StatsBomb data.
        match_dir (Path): The match's `data/euro-2024/{match_id}/` directory.
        missing (list[dict]): Appended to in place when the value can't be read.

    Returns:
        float | None: The team's off_ball.centroid.x, or None.

    Note:
        Match 3930158's Scotland is missing `team_shape_scotland.json`
        entirely (flagged in PR #26 — `extract_team_shape.py`'s own
        `_assert_attacks_right` sanity check raised for that team-match,
        left uninvestigated/unresolved there deliberately). This is handled
        the same as any other missing file — recorded in `missing`, not
        treated as a crash.
    """
    payload = _read_json(match_dir / f"team_shape_{_team_slug(team)}.json")
    if payload is None:
        missing.append({"match_id": match_id, "team": team, "reason": "team_shape_{team}.json not found"})
        return None
    return float(payload["off_ball"]["centroid"]["x"])


_COLLECTORS = {
    "ppda": _collect_ppda,
    "defensive_action_height": _collect_defensive_action_height,
    "block_height": _collect_block_height,
}


def build_reference_distributions(
    match_teams: list[tuple[int, str, str]],
    data_root: Path,
) -> dict:
    """Collect every tercile-labelled measure's value across all team-matches.

    Args:
        match_teams (list[tuple[int, str, str]]): (match_id, home_team,
            away_team) rows, one per match.
        data_root (Path): The `data/euro-2024/` directory (each match's own
            subdirectory is `data_root / str(match_id)`).

    Returns:
        dict: Matches this module's documented JSON output shape, minus
            "metadata" (added by `main`).
    """
    measures: dict[str, dict] = {}
    for measure_name, collector in _COLLECTORS.items():
        values: list[float] = []
        missing: list[dict] = []
        for match_id, home_team, away_team in match_teams:
            match_dir = data_root / str(match_id)
            for team in (home_team, away_team):
                value = collector(match_id, team, match_dir, missing)
                if value is not None:
                    values.append(value)

        sorted_values = sorted(values)
        cut_low, cut_high = tercile_cutpoints(sorted_values)
        measures[measure_name] = {
            "direction": DIRECTIONS[measure_name],
            "n": len(sorted_values),
            "sorted_values": sorted_values,
            "cut_low": cut_low,
            "cut_high": cut_high,
            "missing": missing,
        }

    return {"measures": measures}


def main(data_root: Path | None = None, out_dir: Path | None = None) -> None:
    """Build reference distributions for all 51 Euro 2024 matches and write JSON.

    Args:
        data_root (Path | None): The `data/euro-2024/` directory; defaults to
            the repo's own copy.
        out_dir (Path | None): Output directory; defaults to
            `data/euro-2024/reference/`.

    Output path: {out_dir}/reference_distributions.json
    """
    from statsbombpy import sb

    repo_root = Path(__file__).parents[2]
    if data_root is None:
        data_root = repo_root / "data" / "euro-2024"
    if out_dir is None:
        out_dir = data_root / "reference"
    out_dir.mkdir(parents=True, exist_ok=True)

    matches = sb.matches(competition_id=55, season_id=282)
    match_teams = [
        (int(row["match_id"]), str(row["home_team"]), str(row["away_team"]))
        for _, row in matches.iterrows()
    ]

    payload = build_reference_distributions(match_teams, data_root)
    payload["metadata"] = {
        "definitions_version": DEFINITIONS_VERSION,
        "build_date": date.today().isoformat(),
        "match_count": len(match_teams),
        "competition": "UEFA Euro 2024",
    }

    out_path = out_dir / "reference_distributions.json"
    with open(out_path, "w") as f:
        json.dump(payload, f, indent=2)

    for measure_name, data in payload["measures"].items():
        print(
            f"[{measure_name}] n={data['n']}, missing={len(data['missing'])}, "
            f"cut_low={data['cut_low']}, cut_high={data['cut_high']} -> {out_path}"
        )


if __name__ == "__main__":
    main()
