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
