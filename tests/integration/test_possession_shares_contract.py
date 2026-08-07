"""Integration test: extract_possession_shares() / main() end-to-end against
the real match.
"""

import json
from pathlib import Path

import pytest

from statsbomb.extract_possession_shares import extract_possession_shares, main

pytestmark = pytest.mark.integration


def test_file_is_strict_json_and_has_both_teams(match_id, tmp_path: Path):
    main(match_id=match_id, out_dir=tmp_path)
    text = (tmp_path / f"possession_shares_{match_id}.json").read_text()
    payload = json.loads(text, parse_constant=lambda c: (_ for _ in ()).throw(ValueError(c)))

    assert set(payload["metadata"]["teams"]) == {"Spain", "England"}
    assert len(payload["buckets"]) > 0


def test_buckets_are_ascending_and_end_at_the_final_minute(match_id):
    buckets = extract_possession_shares(match_id)
    minutes = [b["upto_minute"] for b in buckets]
    assert minutes == sorted(minutes)
    assert minutes[-1] >= 90


def test_every_bucket_sums_to_100_across_both_teams(match_id):
    buckets = extract_possession_shares(match_id)
    for bucket in buckets:
        total = sum(bucket["team_possession_pct"].values())
        assert total == pytest.approx(100.0, abs=0.01)


def test_final_bucket_matches_known_whole_match_split(match_id):
    # Cross-check against the same distinct-possession-id method previously
    # verified (manually) for this match: Spain ~51.7%, England ~48.3%.
    buckets = extract_possession_shares(match_id)
    final = buckets[-1]["team_possession_pct"]
    assert final["Spain"] == pytest.approx(51.7, abs=0.5)
    assert final["England"] == pytest.approx(48.3, abs=0.5)
