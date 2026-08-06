"""Integration test: extract_player_heatmap_buckets() end-to-end against the
real match, for Cole Palmer (a late substitute — good coverage for the
"leading buckets skipped until 2+ events exist" behavior) and for the roster
as a whole.
"""

import json
from pathlib import Path

import pytest

from statsbomb.extract_player_heatmap_buckets import extract_player_heatmap_buckets, main
from statsbomb.extract_substitutes import get_eligible_players

pytestmark = pytest.mark.integration

PALMER_ID = 39461


def test_palmer_file_is_strict_json_and_buckets_are_ascending(match_id, tmp_path: Path):
    main(match_id=match_id, out_dir=tmp_path, player_id=PALMER_ID)
    payload = json.loads((tmp_path / "heatmap_buckets" / f"{PALMER_ID}.json").read_text())

    assert payload["metadata"]["display_name"] == "Cole Palmer"
    assert payload["metadata"]["player_id"] == PALMER_ID
    buckets = payload["buckets"]
    assert len(buckets) > 0

    upto_minutes = [b["upto_minute"] for b in buckets]
    assert upto_minutes == sorted(upto_minutes)
    assert len(set(upto_minutes)) == len(upto_minutes)


def test_palmer_buckets_start_after_his_substitution(match_id):
    # Palmer entered as a substitute well after kickoff — no bucket should
    # exist before he had 2+ located events.
    by_player = extract_player_heatmap_buckets(match_id, player_id=PALMER_ID)
    buckets = by_player[PALMER_ID]
    assert buckets[0]["upto_minute"] > 5


def test_bucket_event_counts_are_non_decreasing(match_id):
    by_player = extract_player_heatmap_buckets(match_id, player_id=PALMER_ID)
    counts = [b["event_count"] for b in by_player[PALMER_ID]]
    assert counts == sorted(counts)


def test_every_bucket_grid_matches_configured_dimensions(match_id):
    by_player = extract_player_heatmap_buckets(match_id, player_id=PALMER_ID)
    for bucket in by_player[PALMER_ID]:
        grid = bucket["grid"]
        assert len(grid["values"]) == grid["rows"]
        assert len(grid["values"][0]) == grid["cols"]


def test_every_eligible_player_has_a_key_in_the_result(match_id):
    eligible_ids = set(get_eligible_players(match_id)["player_id"])
    by_player = extract_player_heatmap_buckets(match_id)
    assert set(by_player.keys()) == eligible_ids
