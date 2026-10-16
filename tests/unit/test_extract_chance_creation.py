"""Unit tests for extract_chance_creation's pure classification helpers.
No network calls.
"""

import pandas as pd

from statsbomb.extract_chance_creation import _assist_type, _shot_zone, _source_group


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
