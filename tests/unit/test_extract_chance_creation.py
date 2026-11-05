"""Unit tests for extract_chance_creation's pure classification helpers.
No network calls.
"""

import sys

import pandas as pd

from statsbomb.extract_chance_creation import (
    _assist_type,
    _shot_zone,
    _source_group,
    extract_chance_creation,
)

# `libs/statsbomb/__init__.py` does `from .extract_chance_creation import
# extract_chance_creation`, which rebinds the *package attribute*
# `statsbomb.extract_chance_creation` to the function — so `import
# statsbomb.extract_chance_creation as cc` (or `from statsbomb import
# extract_chance_creation`) resolves to the function, not the module.
# `sys.modules` is unaffected by that clobbering and always has the real
# submodule, which is what a monkeypatch target needs.
cc = sys.modules["statsbomb.extract_chance_creation"]


class TestShotZone:
    def test_six_yard_box(self):
        assert _shot_zone(116.0, 40.0) == "six_yard_box"

    def test_six_yard_box_lower_x_bound(self):
        assert _shot_zone(114.0, 40.0) == "six_yard_box"

    def test_box_central(self):
        # In the box, central band, but outside the six-yard box (x < 114).
        assert _shot_zone(105.0, 40.0) == "box_central"

    def test_box_wide(self):
        # In the box, but y outside the 30-50 central band.
        assert _shot_zone(105.0, 20.0) == "box_wide"

    def test_outside_box(self):
        assert _shot_zone(95.0, 40.0) == "outside_box"

    def test_box_boundary_x_102_is_in_the_box(self):
        assert _shot_zone(102.0, 40.0) == "box_central"

    def test_just_outside_box_boundary(self):
        assert _shot_zone(101.9, 40.0) == "outside_box"

    def test_central_band_boundary_y_30_is_central(self):
        assert _shot_zone(105.0, 30.0) == "box_central"

    def test_central_band_boundary_y_50_is_central(self):
        assert _shot_zone(105.0, 50.0) == "box_central"

    def test_just_above_central_band_is_wide(self):
        assert _shot_zone(105.0, 50.1) == "box_wide"


class TestSourceGroup:
    def test_regular_play_is_open_play(self):
        assert _source_group("Regular Play") == "open_play"

    def test_from_counter_is_counter(self):
        assert _source_group("From Counter") == "counter"

    def test_from_corner_is_set_piece(self):
        assert _source_group("From Corner") == "set_piece"

    def test_from_free_kick_is_set_piece(self):
        assert _source_group("From Free Kick") == "set_piece"

    def test_from_throw_in_is_set_piece(self):
        assert _source_group("From Throw In") == "set_piece"

    def test_unnamed_play_pattern_is_other(self):
        # v3 names only three groups; From Goal Kick/From Keeper/Other/From
        # Kick Off all fall here, kept distinct so totals still foot.
        assert _source_group("From Goal Kick") == "other"
        assert _source_group("From Keeper") == "other"
        assert _source_group("Other") == "other"


class TestAssistType:
    def test_cross_flag(self):
        row = pd.Series({"pass_cross": True, "pass_cut_back": None, "pass_technique": None})
        assert _assist_type(row) == "cross"

    def test_cut_back_flag(self):
        row = pd.Series({"pass_cross": None, "pass_cut_back": True, "pass_technique": None})
        assert _assist_type(row) == "cut_back"

    def test_through_ball_technique(self):
        row = pd.Series({"pass_cross": None, "pass_cut_back": None, "pass_technique": "Through Ball"})
        assert _assist_type(row) == "through_ball"

    def test_cross_checked_before_cut_back(self):
        # First match wins — both flags set is a StatsBomb edge case the
        # spec doesn't disambiguate, so priority order is this module's
        # own documented decision.
        row = pd.Series({"pass_cross": True, "pass_cut_back": True, "pass_technique": None})
        assert _assist_type(row) == "cross"

    def test_no_flags_is_other(self):
        row = pd.Series({"pass_cross": None, "pass_cut_back": None, "pass_technique": "Inswinging"})
        assert _assist_type(row) == "other"

    def test_false_flags_are_other(self):
        row = pd.Series({"pass_cross": False, "pass_cut_back": False, "pass_technique": None})
        assert _assist_type(row) == "other"


class TestExtractChanceCreationMissingAssistColumns:
    """Regression: pass_shot_assist/pass_goal_assist/shot_key_pass_id are
    entirely absent from sb.events() (not just NaN) whenever zero events in
    the whole match set them — statsbombpy's flattening only creates a
    column when at least one event carries it. Found while backfilling
    Euro 2024 reference data: 14 of 51 matches hit this and crashed with
    KeyError before the fix.
    """

    def test_no_crash_when_assist_columns_are_entirely_absent(self, monkeypatch):
        events = pd.DataFrame([
            {
                "id": "shot1", "team": "TeamA", "type": "Shot", "shot_type": "Open Play",
                "location": [110.0, 40.0], "shot_statsbomb_xg": 0.3, "play_pattern": "Regular Play",
            },
            {
                "id": "pass1", "team": "TeamA", "type": "Pass", "location": [50.0, 40.0],
                "play_pattern": "Regular Play", "pass_outcome": None,
                "pass_end_location": [60.0, 40.0], "player_id": 1, "player": "P1",
            },
        ])
        # No pass_shot_assist, pass_goal_assist or shot_key_pass_id column at
        # all — the exact real-world shape that crashed before the fix.
        assert "pass_shot_assist" not in events.columns
        assert "shot_key_pass_id" not in events.columns

        monkeypatch.setattr(cc.sb, "events", lambda match_id: events)
        monkeypatch.setattr(cc, "build_nickname_lookup", lambda match_id: {})

        result = extract_chance_creation(match_id=1, team="TeamA")

        assert result["shots"]["non_penalty_count"] == 1
        assert result["shot_assists"]["total_count"] == 0
        assert result["creators"] == []
