"""Unit tests for statsbomb.utils's pure helpers. No network calls."""

import pandas as pd
import pytest

from statsbomb.utils import (
    SET_PIECE_PLAY_PATTERNS,
    clean_nan,
    end_location,
    open_play_mask,
    parse_timestamp,
    pass_outcome,
)


class TestOpenPlayMask:
    def test_excludes_all_set_piece_patterns(self):
        events = pd.DataFrame({
            "play_pattern": [
                "Regular Play", "From Corner", "From Free Kick",
                "From Goal Kick", "From Kick Off", "From Throw In", "From Counter",
            ]
        })
        mask = open_play_mask(events)
        assert mask.tolist() == [True, False, False, False, False, False, True]

    def test_missing_play_pattern_column_returns_all_true(self):
        events = pd.DataFrame({"type": ["Pass", "Carry"]})
        mask = open_play_mask(events)
        assert mask.tolist() == [True, True]

    def test_set_piece_constant_matches_mask_behavior(self):
        # Every label the mask excludes must be present in the exported constant,
        # so the two can't silently drift apart.
        for pattern in SET_PIECE_PLAY_PATTERNS:
            events = pd.DataFrame({"play_pattern": [pattern]})
            assert open_play_mask(events).tolist() == [False]


class TestParseTimestamp:
    def test_zero(self):
        assert parse_timestamp("00:00:00.000") == 0.0

    def test_minutes_and_seconds(self):
        assert parse_timestamp("00:01:30.500") == pytest.approx(90.5)

    def test_over_one_hour(self):
        # A period's own clock can exceed an hour (extra time); %H must not wrap.
        assert parse_timestamp("01:15:00.000") == pytest.approx(3600 + 15 * 60)


class TestEndLocation:
    def test_pass_returns_end_location(self):
        row = pd.Series({"type": "Pass", "pass_end_location": [100.0, 40.0]})
        assert end_location(row) == (100.0, 40.0)

    def test_carry_returns_end_location(self):
        row = pd.Series({"type": "Carry", "carry_end_location": [55.5, 22.1]})
        assert end_location(row) == (55.5, 22.1)

    def test_shot_returns_end_location(self):
        row = pd.Series({"type": "Shot", "shot_end_location": [120.0, 40.0]})
        assert end_location(row) == (120.0, 40.0)

    def test_other_types_return_none(self):
        row = pd.Series({"type": "Pressure"})
        assert end_location(row) == (None, None)

    def test_missing_end_location_field_returns_none(self):
        row = pd.Series({"type": "Pass"})  # pass_end_location absent
        assert end_location(row) == (None, None)


class TestPassOutcome:
    def test_completed_pass_is_none(self):
        row = pd.Series({"type": "Pass", "pass_outcome": float("nan")})
        assert pass_outcome(row) is None

    def test_incomplete_pass_returns_outcome_string(self):
        row = pd.Series({"type": "Pass", "pass_outcome": "Incomplete"})
        assert pass_outcome(row) == "Incomplete"

    def test_non_pass_type_returns_none(self):
        row = pd.Series({"type": "Carry", "pass_outcome": "Incomplete"})
        assert pass_outcome(row) is None


class TestCleanNan:
    def test_nan_becomes_none(self):
        assert clean_nan(float("nan")) is None

    def test_none_passes_through(self):
        assert clean_nan(None) is None

    def test_zero_is_not_treated_as_missing(self):
        # A naive falsy-check (`if not value`) would wrongly nullify 0.0 —
        # clean_nan must only catch actual NaN, checked via isinstance+isnan.
        assert clean_nan(0.0) == 0.0

    def test_false_is_not_treated_as_missing(self):
        assert clean_nan(False) is False

    def test_string_and_int_pass_through_unchanged(self):
        assert clean_nan("Goal") == "Goal"
        assert clean_nan(42) == 42
