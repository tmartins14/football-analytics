"""Unit tests for extract_defending's pure helpers. No network calls."""

import pandas as pd

from statsbomb.extract_defending import (
    HIGH_TURNOVER_X,
    _defensive_action_height,
    _high_turnovers,
    _is_successful_tackle,
    _win_zone,
)


def _row(**kw) -> pd.Series:
    return pd.Series(kw)


class TestIsSuccessfulTackle:
    def test_won_is_successful(self):
        assert _is_successful_tackle(_row(type="Duel", duel_type="Tackle", duel_outcome="Won")) is True

    def test_success_in_play_is_successful(self):
        # The data has no single clean "success" value for a Tackle — both
        # "Won" and "Success In Play" occur and both count (AUDIT-v3.md item 5,
        # Tyler's decision on the open question it raised).
        assert _is_successful_tackle(
            _row(type="Duel", duel_type="Tackle", duel_outcome="Success In Play")
        ) is True

    def test_lost_in_play_is_not_successful(self):
        assert _is_successful_tackle(
            _row(type="Duel", duel_type="Tackle", duel_outcome="Lost In Play")
        ) is False

    def test_lost_out_is_not_successful(self):
        assert _is_successful_tackle(
            _row(type="Duel", duel_type="Tackle", duel_outcome="Lost Out")
        ) is False

    def test_aerial_lost_duel_type_is_not_a_tackle(self):
        assert _is_successful_tackle(
            _row(type="Duel", duel_type="Aerial Lost", duel_outcome="Won")
        ) is False

    def test_non_duel_event_is_not_a_tackle(self):
        assert _is_successful_tackle(_row(type="Interception", duel_type=None, duel_outcome=None)) is False


class TestDefensiveActionHeight:
    def test_mean_of_credited_types(self):
        events = pd.DataFrame([
            {"team": "Spain", "type": "Ball Recovery", "location": [20.0, 40.0], "duel_type": None, "duel_outcome": None},
            {"team": "Spain", "type": "Clearance", "location": [40.0, 40.0], "duel_type": None, "duel_outcome": None},
            {"team": "Spain", "type": "Duel", "location": [60.0, 40.0], "duel_type": "Tackle", "duel_outcome": "Won"},
            # Failed tackle and a different team's event must not count.
            {"team": "Spain", "type": "Duel", "location": [100.0, 40.0], "duel_type": "Tackle", "duel_outcome": "Lost Out"},
            {"team": "England", "type": "Ball Recovery", "location": [10.0, 40.0], "duel_type": None, "duel_outcome": None},
        ])
        result = _defensive_action_height(events, "Spain")
        assert result == {"mean_x": 40.0, "n_actions": 3}

    def test_no_actions_is_null_mean(self):
        events = pd.DataFrame([
            {"team": "England", "type": "Ball Recovery", "location": [10.0, 40.0], "duel_type": None, "duel_outcome": None},
        ])
        result = _defensive_action_height(events, "Spain")
        assert result == {"mean_x": None, "n_actions": 0}


class TestHighTurnovers:
    def test_at_threshold_counts(self):
        events = pd.DataFrame([
            {"team": "Spain", "possession_team": "Spain", "possession": 1,
             "type": "Ball Recovery", "play_pattern": "Regular Play", "location": [HIGH_TURNOVER_X, 40.0]},
        ])
        result = _high_turnovers(events, "Spain")
        assert result == {"count": 1, "ended_in_shot": 0}

    def test_just_below_threshold_does_not_count(self):
        events = pd.DataFrame([
            {"team": "Spain", "possession_team": "Spain", "possession": 1,
             "type": "Ball Recovery", "play_pattern": "Regular Play", "location": [HIGH_TURNOVER_X - 0.1, 40.0]},
        ])
        result = _high_turnovers(events, "Spain")
        assert result == {"count": 0, "ended_in_shot": 0}

    def test_set_piece_restart_does_not_count(self):
        events = pd.DataFrame([
            {"team": "Spain", "possession_team": "Spain", "possession": 1,
             "type": "Pass", "play_pattern": "From Goal Kick", "location": [80.0, 40.0]},
        ])
        result = _high_turnovers(events, "Spain")
        assert result == {"count": 0, "ended_in_shot": 0}

    def test_ended_in_shot_is_counted_when_a_later_shot_shares_the_possession_id(self):
        events = pd.DataFrame([
            {"team": "Spain", "possession_team": "Spain", "possession": 1,
             "type": "Ball Recovery", "play_pattern": "Regular Play", "location": [80.0, 40.0]},
            {"team": "Spain", "possession_team": "Spain", "possession": 1,
             "type": "Shot", "play_pattern": "Regular Play", "location": [110.0, 40.0]},
        ])
        result = _high_turnovers(events, "Spain")
        assert result == {"count": 1, "ended_in_shot": 1}

    def test_only_the_earliest_event_in_the_possession_is_checked(self):
        # The first event (by row order) is deep in the team's own half —
        # a later event in the same possession being advanced must not
        # retroactively count as the turnover point.
        events = pd.DataFrame([
            {"team": "Spain", "possession_team": "Spain", "possession": 1,
             "type": "Ball Recovery", "play_pattern": "Regular Play", "location": [20.0, 40.0]},
            {"team": "Spain", "possession_team": "Spain", "possession": 1,
             "type": "Carry", "play_pattern": "Regular Play", "location": [90.0, 40.0]},
        ])
        result = _high_turnovers(events, "Spain")
        assert result == {"count": 0, "ended_in_shot": 0}

    def test_opponent_event_within_the_same_possession_id_is_skipped(self):
        # A stray opponent event tagged under this possession id (e.g. a
        # failed challenge) must not be mistaken for "the team's own first
        # event" — the earliest *own-team* event is what's checked.
        events = pd.DataFrame([
            {"team": "England", "possession_team": "Spain", "possession": 1,
             "type": "Duel", "play_pattern": "Regular Play", "location": [20.0, 40.0]},
            {"team": "Spain", "possession_team": "Spain", "possession": 1,
             "type": "Ball Recovery", "play_pattern": "Regular Play", "location": [80.0, 40.0]},
        ])
        result = _high_turnovers(events, "Spain")
        assert result == {"count": 1, "ended_in_shot": 0}


class TestWinZone:
    def test_counts_by_band(self):
        events = pd.DataFrame([
            {"team": "Spain", "type": "Ball Recovery", "location": [10.0, 40.0], "duel_type": None, "duel_outcome": None},
            {"team": "Spain", "type": "Interception", "location": [50.0, 40.0], "duel_type": None, "duel_outcome": None},
            {"team": "Spain", "type": "Duel", "location": [70.0, 40.0], "duel_type": "Tackle", "duel_outcome": "Won"},
            {"team": "Spain", "type": "Duel", "location": [90.0, 40.0], "duel_type": "Tackle", "duel_outcome": "Success In Play"},
            # Failed tackle, a Clearance (not a win_zone type), and an
            # opponent event must all be excluded.
            {"team": "Spain", "type": "Duel", "location": [100.0, 40.0], "duel_type": "Tackle", "duel_outcome": "Lost Out"},
            {"team": "Spain", "type": "Clearance", "location": [30.0, 40.0], "duel_type": None, "duel_outcome": None},
            {"team": "England", "type": "Ball Recovery", "location": [10.0, 40.0], "duel_type": None, "duel_outcome": None},
        ])
        result = _win_zone(events, "Spain")
        assert result == {"own_third": 1, "own_half": 1, "opposition_half": 1, "final_third": 1}
