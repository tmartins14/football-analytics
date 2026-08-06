"""Unit tests for extract_player_events's pure per-event helpers. No network calls."""

import pandas as pd

from statsbomb.extract_player_events import _event_outcome, _key_pass, _pressure_regain, _shot_fields


class TestEventOutcome:
    def test_pass_dispatches_to_pass_outcome(self):
        completed = pd.Series({"type": "Pass", "pass_outcome": float("nan")})
        incomplete = pd.Series({"type": "Pass", "pass_outcome": "Out"})
        assert _event_outcome(completed) is None
        assert _event_outcome(incomplete) == "Out"

    def test_duel(self):
        won = pd.Series({"type": "Duel", "duel_outcome": "Won"})
        assert _event_outcome(won) == "Won"

    def test_interception(self):
        row = pd.Series({"type": "Interception", "interception_outcome": "Success In Play"})
        assert _event_outcome(row) == "Success In Play"

    def test_dribble(self):
        row = pd.Series({"type": "Dribble", "dribble_outcome": "Incomplete"})
        assert _event_outcome(row) == "Incomplete"

    def test_shot(self):
        row = pd.Series({"type": "Shot", "shot_outcome": "Goal"})
        assert _event_outcome(row) == "Goal"

    def test_ball_recovery_failure(self):
        row = pd.Series({"type": "Ball Recovery", "ball_recovery_recovery_failure": True})
        assert _event_outcome(row) == "Failure"

    def test_ball_recovery_success_has_no_outcome_field(self):
        row = pd.Series({"type": "Ball Recovery", "ball_recovery_recovery_failure": float("nan")})
        assert _event_outcome(row) is None

    def test_types_with_no_outcome_field_return_none(self):
        for event_type in ("Carry", "Clearance", "Block", "Pressure", "Dispossessed", "Miscontrol"):
            row = pd.Series({"type": event_type})
            assert _event_outcome(row) is None, event_type


class TestPressureRegain:
    def test_possession_flips_to_pressing_team_within_window(self):
        row = pd.Series({"team": "England", "possession_team": "Spain", "minute": 70, "second": 0, "period": 2})
        all_events = pd.DataFrame([
            {"period": 2, "minute": 70, "second": 0, "possession_team": "Spain"},
            {"period": 2, "minute": 70, "second": 3, "possession_team": "England"},
        ])
        assert _pressure_regain(row, all_events) is True

    def test_possession_stays_with_the_other_team(self):
        row = pd.Series({"team": "England", "possession_team": "Spain", "minute": 70, "second": 0, "period": 2})
        all_events = pd.DataFrame([
            {"period": 2, "minute": 70, "second": 0, "possession_team": "Spain"},
            {"period": 2, "minute": 70, "second": 3, "possession_team": "Spain"},
        ])
        assert _pressure_regain(row, all_events) is False

    def test_possession_already_belonged_to_pressing_team(self):
        # A same-team "flip" (no real change) must not count as a regain.
        row = pd.Series({"team": "England", "possession_team": "England", "minute": 70, "second": 0, "period": 2})
        all_events = pd.DataFrame([
            {"period": 2, "minute": 70, "second": 0, "possession_team": "England"},
            {"period": 2, "minute": 70, "second": 3, "possession_team": "England"},
        ])
        assert _pressure_regain(row, all_events) is False

    def test_flip_outside_the_window_does_not_count(self):
        row = pd.Series({"team": "England", "possession_team": "Spain", "minute": 70, "second": 0, "period": 2})
        all_events = pd.DataFrame([
            {"period": 2, "minute": 70, "second": 0, "possession_team": "Spain"},
            {"period": 2, "minute": 70, "second": 10, "possession_team": "England"},  # 10s > default 5s window
        ])
        assert _pressure_regain(row, all_events) is False

    def test_half_time_boundary_regression(self):
        # Second-half StatsBomb clocks restart around ~45' rather than continuing
        # from where the first half ended — so a period-1 event near 45' and a
        # period-2 event near 45' can have near-identical minute*60+second
        # values despite the halftime break between them in real time. The
        # window must be bounded to the SAME period, or this pair would
        # wrongly register as a regain 3 seconds later.
        row = pd.Series({"team": "England", "possession_team": "Spain", "minute": 45, "second": 0, "period": 1})
        all_events = pd.DataFrame([
            {"period": 1, "minute": 45, "second": 0, "possession_team": "Spain"},
            {"period": 2, "minute": 45, "second": 3, "possession_team": "England"},
        ])
        assert _pressure_regain(row, all_events) is False

    def test_custom_window_seconds(self):
        row = pd.Series({"team": "England", "possession_team": "Spain", "minute": 70, "second": 0, "period": 2})
        all_events = pd.DataFrame([
            {"period": 2, "minute": 70, "second": 0, "possession_team": "Spain"},
            {"period": 2, "minute": 70, "second": 8, "possession_team": "England"},
        ])
        assert _pressure_regain(row, all_events, window_seconds=5) is False
        assert _pressure_regain(row, all_events, window_seconds=10) is True


class TestShotFields:
    def test_goal_has_xg_end_location_and_is_goal_true(self):
        row = pd.Series({
            "type": "Shot",
            "shot_statsbomb_xg": 0.32145,
            "shot_end_location": [120.0, 40.0, 2.1],
            "shot_outcome": "Goal",
        })
        xg, end_loc, is_goal = _shot_fields(row)
        assert xg == 0.32145
        assert end_loc == [120.0, 40.0, 2.1]
        assert is_goal is True

    def test_off_target_shot_is_not_a_goal(self):
        row = pd.Series({
            "type": "Shot",
            "shot_statsbomb_xg": 0.05,
            "shot_end_location": [121.0, 38.0, 3.4],
            "shot_outcome": "Off T",
        })
        _, _, is_goal = _shot_fields(row)
        assert is_goal is False

    def test_non_shot_returns_all_none(self):
        row = pd.Series({"type": "Pass", "shot_statsbomb_xg": 0.9})
        assert _shot_fields(row) == (None, None, None)

    def test_missing_xg_is_none_not_nan(self):
        row = pd.Series({
            "type": "Shot",
            "shot_statsbomb_xg": float("nan"),
            "shot_end_location": [120.0, 40.0],
            "shot_outcome": "Saved",
        })
        xg, _, _ = _shot_fields(row)
        assert xg is None


class TestKeyPass:
    def test_shot_assist_is_key_pass(self):
        row = pd.Series({"type": "Pass", "pass_shot_assist": True, "pass_goal_assist": float("nan")})
        assert _key_pass(row) is True

    def test_goal_assist_is_key_pass(self):
        row = pd.Series({"type": "Pass", "pass_shot_assist": float("nan"), "pass_goal_assist": True})
        assert _key_pass(row) is True

    def test_ordinary_pass_is_not_key_pass(self):
        row = pd.Series({"type": "Pass", "pass_shot_assist": float("nan"), "pass_goal_assist": float("nan")})
        assert _key_pass(row) is False

    def test_non_pass_returns_none(self):
        row = pd.Series({"type": "Carry"})
        assert _key_pass(row) is None
