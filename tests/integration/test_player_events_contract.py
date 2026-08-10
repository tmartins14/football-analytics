"""Integration test: extract_player_events() end-to-end against the real match,
for Cole Palmer (the substitute whose short, event-dense window this session
used for manual verification while building the extractor).
"""

import json
from pathlib import Path

import pytest

from statsbomb.extract_player_events import extract_player_events, main

pytestmark = pytest.mark.integration

PALMER_ID = 39461


def _strict_json_loads(text: str):
    """Parse JSON rejecting NaN/Infinity/-Infinity tokens (Python's json module
    accepts them by default as a non-standard extension; JS's JSON.parse does
    not — this simulates the stricter behavior the tylermartins.com consumer
    will actually see).
    """
    def _reject(constant):
        raise ValueError(f"invalid JSON constant token: {constant!r}")

    return json.loads(text, parse_constant=_reject)


def test_palmer_file_is_strict_json_with_no_nan_tokens(match_id, tmp_path: Path):
    main(match_id=match_id, out_dir=tmp_path, player_id=PALMER_ID)
    text = (tmp_path / "player_events" / f"{PALMER_ID}.json").read_text()
    payload = _strict_json_loads(text)

    assert payload["metadata"]["display_name"] == "Cole Palmer"
    assert payload["metadata"]["player_id"] == PALMER_ID
    assert len(payload["events"]) == payload["metadata"]["n_events"]


def test_palmer_scored_exactly_one_goal(match_id):
    df = extract_player_events(match_id, player_id=PALMER_ID)
    goals = df[(df["type"] == "Shot") & (df["outcome"] == "Goal")]
    assert len(goals) == 1


def test_palmer_goal_has_xg_and_is_goal_and_end_location(match_id):
    df = extract_player_events(match_id, player_id=PALMER_ID)
    goal = df[(df["type"] == "Shot") & (df["outcome"] == "Goal")].iloc[0]
    assert goal["is_goal"] is True
    assert goal["shot_xg"] is not None and goal["shot_xg"] > 0
    assert isinstance(goal["shot_end_location"], list) and len(goal["shot_end_location"]) >= 2


def test_non_shot_rows_have_no_shot_fields(match_id):
    df = extract_player_events(match_id, player_id=PALMER_ID)
    non_shots = df[df["type"] != "Shot"]
    assert non_shots["shot_xg"].isna().all()
    assert non_shots["is_goal"].isna().all()


def test_non_pass_rows_have_no_key_pass_field(match_id):
    df = extract_player_events(match_id, player_id=PALMER_ID)
    non_passes = df[df["type"] != "Pass"]
    assert non_passes["key_pass"].isna().all()


def test_every_pass_and_carry_has_an_xt_delta(match_id):
    df = extract_player_events(match_id, player_id=PALMER_ID)
    pass_carry = df[df["type"].isin(["Pass", "Carry"])]
    assert len(pass_carry) > 0
    assert pass_carry["xt_delta"].notna().all()


def test_no_fabricated_tackle_type(match_id):
    # "Tackle" is a duel_type qualifier, not a StatsBomb `type` — regression
    # test for including it as a top-level type in an earlier draft.
    df = extract_player_events(match_id, player_id=PALMER_ID)
    assert "Tackle" not in df["type"].values
    assert (df.loc[df["type"] == "Duel", "duel_type"] == "Tackle").any()


def test_palmer_has_an_assisted_pass_with_positive_xg(match_id):
    # Palmer's assist during his own substitute cameo — exercises the
    # pass_assisted_shot_id join end-to-end against real data.
    df = extract_player_events(match_id, player_id=PALMER_ID)
    assisted = df[df["assisted_shot_xg"].notna()]
    assert len(assisted) >= 1
    assert (assisted["assisted_shot_xg"] > 0).all()


def test_non_pass_rows_have_no_assisted_shot_xg(match_id):
    df = extract_player_events(match_id, player_id=PALMER_ID)
    non_passes = df[df["type"] != "Pass"]
    assert non_passes["assisted_shot_xg"].isna().all()


def test_possession_shot_xg_is_never_null_and_sometimes_positive(match_id):
    df = extract_player_events(match_id, player_id=PALMER_ID)
    assert df["possession_shot_xg"].notna().all()
    # Palmer scored, so at least one of his own events sits in a possession
    # that produced a shot.
    assert (df["possession_shot_xg"] > 0).any()
