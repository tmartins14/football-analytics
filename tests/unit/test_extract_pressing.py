"""Unit tests for extract_pressing's pure filter helpers. No network calls."""

import pandas as pd

from statsbomb.extract_pressing import _defensive_action_mask, _open_play_pass_mask


def _events(rows):
    return pd.DataFrame(rows)


class TestOpenPlayPassMask:
    def test_regular_play_pass_with_no_pass_type_is_open_play(self):
        df = _events([
            {"type": "Pass", "play_pattern": "Regular Play", "pass_type": None},
        ])
        assert list(_open_play_pass_mask(df)) == [True]

    def test_from_counter_pass_is_open_play(self):
        df = _events([
            {"type": "Pass", "play_pattern": "From Counter", "pass_type": None},
        ])
        assert list(_open_play_pass_mask(df)) == [True]

    def test_from_corner_play_pattern_is_excluded(self):
        df = _events([
            {"type": "Pass", "play_pattern": "From Corner", "pass_type": "Corner"},
        ])
        assert list(_open_play_pass_mask(df)) == [False]

    def test_regular_play_but_corner_pass_type_is_excluded(self):
        # A short-corner routine's restart pass can carry play_pattern
        # "Regular Play" once possession resumes, but pass_type still marks
        # it as the restart itself — both checks must hold, not just one.
        df = _events([
            {"type": "Pass", "play_pattern": "Regular Play", "pass_type": "Corner"},
        ])
        assert list(_open_play_pass_mask(df)) == [False]

    def test_from_keeper_play_pattern_is_excluded(self):
        # v3's own Open Play definition is {Regular Play, From Counter} only
        # — stricter than utils.open_play_mask, which would admit this.
        df = _events([
            {"type": "Pass", "play_pattern": "From Keeper", "pass_type": None},
        ])
        assert list(_open_play_pass_mask(df)) == [False]

    def test_non_pass_event_is_excluded(self):
        df = _events([
            {"type": "Carry", "play_pattern": "Regular Play", "pass_type": None},
        ])
        assert list(_open_play_pass_mask(df)) == [False]


class TestDefensiveActionMask:
    def test_tackle_duel_any_outcome_counts(self):
        df = _events([
            {"type": "Duel", "duel_type": "Tackle"},
        ])
        assert list(_defensive_action_mask(df)) == [True]

    def test_aerial_lost_duel_does_not_count(self):
        df = _events([
            {"type": "Duel", "duel_type": "Aerial Lost"},
        ])
        assert list(_defensive_action_mask(df)) == [False]

    def test_interception_counts(self):
        df = _events([
            {"type": "Interception", "duel_type": None},
        ])
        assert list(_defensive_action_mask(df)) == [True]

    def test_foul_committed_counts(self):
        df = _events([
            {"type": "Foul Committed", "duel_type": None},
        ])
        assert list(_defensive_action_mask(df)) == [True]

    def test_pressure_does_not_count(self):
        # Pressure is its own, separate measure (pressures_high) — not a
        # PPDA denominator action.
        df = _events([
            {"type": "Pressure", "duel_type": None},
        ])
        assert list(_defensive_action_mask(df)) == [False]
