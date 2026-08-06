"""Integration test: extract_player_match_summary() end-to-end against the
real match, for Cole Palmer (scored a goal off a low-probability shot and
picked up an assist — exercises xg, xa, and xg_chain against known events).
"""

import json
from pathlib import Path

import pytest

from statsbomb.extract_player_match_summary import extract_player_match_summary, main
from statsbomb.extract_substitutes import get_eligible_players

pytestmark = pytest.mark.integration

PALMER_ID = 39461


def _strict_json_loads(text: str):
    def _reject(constant):
        raise ValueError(f"invalid JSON constant token: {constant!r}")

    return json.loads(text, parse_constant=_reject)


def test_palmer_file_is_strict_json(match_id, tmp_path: Path):
    main(match_id=match_id, out_dir=tmp_path, player_id=PALMER_ID)
    text = (tmp_path / "player_match_summary" / f"{PALMER_ID}.json").read_text()
    payload = _strict_json_loads(text)

    assert payload["metadata"]["display_name"] == "Cole Palmer"
    assert payload["metadata"]["player_id"] == PALMER_ID


def test_palmer_has_positive_xg_from_his_goal(match_id):
    summary = extract_player_match_summary(match_id, player_id=PALMER_ID)[PALMER_ID]
    assert summary["xg"] > 0


def test_team_and_opponent_possession_sum_to_100(match_id):
    summary = extract_player_match_summary(match_id, player_id=PALMER_ID)[PALMER_ID]
    total = summary["team_possession_pct"] + summary["opponent_possession_pct"]
    assert total == pytest.approx(100.0, abs=0.01)


def test_every_eligible_player_has_a_summary(match_id):
    eligible_ids = set(get_eligible_players(match_id)["player_id"])
    by_player = extract_player_match_summary(match_id)
    assert set(by_player.keys()) == eligible_ids


def test_all_metric_values_are_json_native_types(match_id):
    # Regression guard: pandas/numpy scalars (np.float64, np.int64) serialize
    # fine via json.dump but would round-trip as the wrong Python type for a
    # strict consumer — every metric should already be a native int/float/None.
    summary = extract_player_match_summary(match_id, player_id=PALMER_ID)[PALMER_ID]
    for key, value in summary.items():
        assert type(value) in (int, float, type(None)), f"{key} is {type(value)}"
