"""Unit tests for extract_substitutes.get_eligible_players.

Synthetic data only — sb.lineups()/sb.events() are monkeypatched to a small
hand-built roster, so this exercises the tricky roster-building logic without
any network call. (The real-data version of this coverage — confirming the
function's output against the actual Euro 2024 Final roster — lives in
tests/integration/test_roster_matches_known_match.py.)
"""

import json

import pandas as pd
import pytest

from statsbomb import extract_substitutes


def _position(position, start_reason, from_="00:00", to=None):
    return {
        "position": position,
        "from": from_,
        "to": to,
        "from_period": 1,
        "to_period": 1,
        "start_reason": start_reason,
        "end_reason": None,
    }


def _lineup_row(player_id, player_name, jersey_number, positions, nickname=None):
    return {
        "player_id": player_id,
        "player_name": player_name,
        "player_nickname": nickname if nickname is not None else float("nan"),
        "jersey_number": jersey_number,
        "country": "Testland",
        "cards": [],
        "positions": positions,
    }


@pytest.fixture
def synthetic_roster(monkeypatch):
    """Patch sb.lineups()/sb.events() with a small hand-built roster.

    TeamA:
      1  Test Keeper    - starting GK, must be excluded.
      2  Test Defender  - starting outfield, included as a starter.
      3  Test Sub       - substitute with a matching Substitution event, and
                          deliberately NO Tactical Shift event anywhere in the
                          synthetic event table — get_eligible_players must not
                          depend on one existing to find this player.
      4  Test Bench     - never played (empty positions list), excluded.
      5  Test Hybrid    - played Center Back then Goalkeeper; excluded entirely
                          because ANY position entry is "Goalkeeper".
      6  Test Ghost Sub - substitute with no matching Substitution event row
                          (a data-quality edge case); must not crash.

    Returns:
        pd.DataFrame: get_eligible_players()'s output for this synthetic roster.
    """
    lineups = {
        "TeamA": pd.DataFrame([
            _lineup_row(1, "Test Keeper", 1, [_position("Goalkeeper", "Starting XI")]),
            _lineup_row(2, "Test Defender", 4, [_position("Center Back", "Starting XI")]),
            _lineup_row(3, "Test Sub", 17, [_position("Right Wing", "Substitution - On")]),
            _lineup_row(4, "Test Bench", 22, []),
            _lineup_row(5, "Test Hybrid", 5, [
                _position("Center Back", "Starting XI", to="60:00"),
                _position("Goalkeeper", "Tactical Shift", from_="60:00"),
            ]),
            _lineup_row(6, "Test Ghost Sub", 19, [_position("Left Back", "Substitution - On")]),
        ]),
    }

    events = pd.DataFrame([
        {
            "type": "Substitution", "team": "TeamA", "player": "Test Departing Player",
            "substitution_replacement": "Test Sub", "minute": 70, "second": 12,
        },
        # No Tactical Shift row at all, and no Substitution row for "Test Ghost Sub".
    ])

    monkeypatch.setattr(extract_substitutes.sb, "lineups", lambda match_id: lineups)
    monkeypatch.setattr(extract_substitutes.sb, "events", lambda match_id: events)
    # main() also calls fetch_match_info(), which otherwise hits sb.competitions()/
    # sb.matches() live for the fake match_id — patch it too so this stays a
    # genuine unit test (no network calls at all), not just the roster lookups.
    monkeypatch.setattr(
        extract_substitutes, "fetch_match_info",
        lambda match_id: ("Test Competition", "2024", "TeamA vs TeamB"),
    )

    return extract_substitutes.get_eligible_players(match_id=999999)


class TestGetEligiblePlayers:
    def test_excludes_players_who_never_played(self, synthetic_roster):
        assert "Test Bench" not in synthetic_roster["display_name"].values

    def test_excludes_goalkeepers(self, synthetic_roster):
        assert "Test Keeper" not in synthetic_roster["display_name"].values

    def test_excludes_hybrid_players_with_any_goalkeeper_spell(self, synthetic_roster):
        assert "Test Hybrid" not in synthetic_roster["display_name"].values

    def test_includes_the_starting_outfield_player(self, synthetic_roster):
        row = synthetic_roster[synthetic_roster["display_name"] == "Test Defender"].iloc[0]
        assert row["is_starter"]
        # on_minute/on_second are float64 NaN at the DataFrame level (pandas'
        # standard missing-numeric representation, matching pd.notna() checks
        # used throughout this codebase e.g. in utils.pass_outcome) — main()
        # converts NaN -> JSON null explicitly before serializing; see
        # test_extract_player_events.py / the integration tests for that step.
        assert pd.isna(row["on_minute"])

    def test_substitute_without_a_tactical_shift_is_still_included(self, synthetic_roster):
        # No Tactical Shift event exists anywhere in the synthetic table, yet the
        # substitute is found and correctly cross-referenced to their
        # Substitution event — this is the exact case that silently dropped 4 of
        # 7 real substitutes when formation periods were used as the roster
        # source instead.
        row = synthetic_roster[synthetic_roster["display_name"] == "Test Sub"].iloc[0]
        assert not row["is_starter"]
        assert row["on_minute"] == 70
        assert row["on_second"] == 12
        assert row["replaced_player"] == "Test Departing Player"

    def test_substitute_with_no_matching_event_row_does_not_crash(self, synthetic_roster):
        row = synthetic_roster[synthetic_roster["display_name"] == "Test Ghost Sub"].iloc[0]
        assert not row["is_starter"]
        assert pd.isna(row["on_minute"])
        assert pd.isna(row["on_second"])
        # Surprising but real pandas behavior, verified empirically while writing
        # this test: None mixed with real strings in an object column can ALSO
        # come back as NaN, not just numeric columns — this is exactly why
        # extract_substitutes.main() now runs every field through
        # utils.clean_nan() before json.dump, not just on_minute/on_second.
        assert pd.isna(row["replaced_player"])

    def test_eligible_count(self, synthetic_roster):
        # Keeper, Bench, and Hybrid excluded — Defender, Sub, and Ghost Sub remain.
        assert len(synthetic_roster) == 3

    def test_player_id_present_on_every_row(self, synthetic_roster):
        assert synthetic_roster["player_id"].tolist() == sorted(synthetic_roster["player_id"].tolist())
        assert set(synthetic_roster["player_id"]) == {2, 3, 6}


class TestExtractSubstitutes:
    def test_returns_only_non_starters(self, synthetic_roster):
        # Depending on the synthetic_roster fixture (ignoring its return value)
        # keeps sb.lineups()/sb.events() monkeypatched for this direct call —
        # extract_substitutes() re-derives its own roster via
        # get_eligible_players() internally, using the same active patch.
        result = extract_substitutes.extract_substitutes(match_id=999999)
        assert set(result["display_name"]) == {"Test Sub", "Test Ghost Sub"}
        assert not result["is_starter"].any()


class TestMainWritesCleanJson:
    def test_no_nan_tokens_and_replaced_player_is_null_for_unmatched_sub(
        self, synthetic_roster, tmp_path
    ):
        # Regression test for the bug the tests above surfaced: a substitute
        # with no matching Substitution event has replaced_player == NaN at the
        # DataFrame level (not just on_minute/on_second) — main() must clean
        # every field, not just the two numeric ones, or json.dump emits an
        # invalid literal NaN token for replaced_player here.
        extract_substitutes.main(match_id=999999, out_dir=tmp_path)
        payload = json.loads((tmp_path / "substitutes.json").read_text())

        ghost = next(
            p for p in payload["teams"]["TeamA"] if p["display_name"] == "Test Ghost Sub"
        )
        assert ghost["replaced_player"] is None
        assert ghost["on_minute"] is None
        assert ghost["on_second"] is None

        matched = next(
            p for p in payload["teams"]["TeamA"] if p["display_name"] == "Test Sub"
        )
        assert matched["on_minute"] == 70
        assert isinstance(matched["on_minute"], int)
