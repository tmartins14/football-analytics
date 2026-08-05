"""Unit tests for extract_progressive_map's pure geometry helpers. No network calls."""

import math

import pytest

from statsbomb.extract_progressive_map import _dist_to_goal, _is_progressive


class TestDistToGoal:
    def test_at_goal_centre_is_zero(self):
        assert _dist_to_goal(120.0, 40.0) == 0.0

    def test_along_the_x_axis(self):
        assert _dist_to_goal(0.0, 40.0) == pytest.approx(120.0)

    def test_along_the_y_axis(self):
        assert _dist_to_goal(120.0, 0.0) == pytest.approx(40.0)

    def test_diagonal(self):
        assert _dist_to_goal(0.0, 0.0) == pytest.approx(math.sqrt(120.0**2 + 40.0**2))


class TestIsProgressive:
    def test_exactly_at_threshold_is_progressive(self):
        # d_start = 100 (point (20, 40)); d_end = 75 (point (45, 40)) — exactly
        # 25% of the remaining distance closed, the boundary the "<=" comparison
        # must include.
        assert _is_progressive(20.0, 40.0, 45.0, 40.0) is True

    def test_just_short_of_threshold_is_not_progressive(self):
        assert _is_progressive(20.0, 40.0, 44.9, 40.0) is False

    def test_gains_distance_but_not_enough_is_not_progressive(self):
        # d_start = 100, d_end = 90 — 10 yards closer, but well short of 25%.
        assert _is_progressive(20.0, 40.0, 30.0, 40.0) is False

    def test_moves_away_from_goal_is_not_progressive(self):
        assert _is_progressive(20.0, 40.0, 5.0, 40.0) is False

    def test_starting_at_goal_centre_is_not_progressive(self):
        # d_start == 0 guard — must not divide by zero, must return False.
        assert _is_progressive(120.0, 40.0, 110.0, 40.0) is False

    def test_custom_threshold(self):
        # d_start = 100 (point (20, 40)). A 60% threshold requires d_end <= 40.
        assert _is_progressive(20.0, 40.0, 45.0, 40.0, threshold=0.6) is False  # d_end=75
        assert _is_progressive(20.0, 40.0, 85.0, 40.0, threshold=0.6) is True   # d_end=35
