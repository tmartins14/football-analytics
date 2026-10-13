"""Unit tests for tactical_definitions's coordinate edges. No network calls."""

import pytest

from statsbomb.tactical_definitions import band_for_x, lane_for_y


class TestLaneForY:
    def test_lower_bound_is_inclusive(self):
        assert lane_for_y(0) == "left_wing"

    def test_boundary_is_half_open_lands_in_the_upper_bucket(self):
        # y=18 is the left_wing/left_half_space edge. Half-open [low, high)
        # means the boundary value belongs to the bucket it's the *low* end
        # of, not the one it's the high end of.
        assert lane_for_y(18) == "left_half_space"

    def test_right_wing_is_closed_on_its_upper_bound(self):
        # Every other bucket's upper bound is open (owned by the next
        # bucket), but right_wing is the last one — its upper bound (the
        # far touchline, y=80) must belong to it, not raise.
        assert lane_for_y(80) == "right_wing"

    def test_centre_of_pitch(self):
        assert lane_for_y(40) == "centre"

    @pytest.mark.parametrize("y", [-0.1, 80.1, -5, 100])
    def test_outside_the_pitch_raises(self, y):
        with pytest.raises(ValueError):
            lane_for_y(y)


class TestBandForX:
    def test_lower_bound_is_inclusive(self):
        assert band_for_x(0) == "own_third"

    def test_boundary_is_half_open_lands_in_the_upper_bucket(self):
        assert band_for_x(40) == "own_half"

    def test_final_third_is_closed_on_its_upper_bound(self):
        # The far goal line (x=120) must belong to final_third, not raise.
        assert band_for_x(120) == "final_third"

    def test_opposition_half(self):
        assert band_for_x(70) == "opposition_half"

    @pytest.mark.parametrize("x", [-0.1, 120.1, -5, 200])
    def test_outside_the_pitch_raises(self, x):
        with pytest.raises(ValueError):
            band_for_x(x)
