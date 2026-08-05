"""Integration test: extract_formation() emits player_id — a regression test for
the additive field added to this already-shipped extractor this session (needed
so a clicked Starting XI marker can be resolved to a per-player events file).
"""

import pytest

from statsbomb.extract_formation import extract_formation

pytestmark = pytest.mark.integration


def test_every_player_record_has_an_integer_player_id(match_id):
    df = extract_formation(match_id, "England")
    assert "player_id" in df.columns
    assert df["player_id"].notna().all()
    assert all(isinstance(v, (int,)) or float(v).is_integer() for v in df["player_id"])


def test_player_id_matches_known_players(match_id):
    df = extract_formation(match_id, "England")
    by_name = dict(zip(df["display_name"], df["player_id"]))
    assert by_name["Jordan Pickford"] == 3468
