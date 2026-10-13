"""Unit tests for extract_team_shape's pure per-dot/per-period helpers.

No network calls — synthetic frames and a synthetic events DataFrame only.
Covers Part 0 of DATA-SPEC-v2: the opponent-actor mirror, keeper exclusion,
the attack-direction sanity check, and lane_counts/band_counts.
"""

import pandas as pd
import pytest

from statsbomb.extract_team_shape import (
    _assert_attacks_right,
    _mirror_xy,
    _off_ball_dot_xy,
    _on_ball_periods,
)


class TestMirrorXy:
    def test_point_reflection(self):
        assert _mirror_xy(100, 10) == (20, 70)

    def test_centre_spot_is_a_fixed_point(self):
        assert _mirror_xy(60, 40) == (60, 40)


class TestOffBallDotXy:
    """DATA-SPEC-v2 Part 0, step 1's own example: an opponent-actor dot at
    x=100 lands at x=20; an own-actor dot at x=30 stays at 30. Per the
    teammate-boolean inversion (module docstring), when the actor is the
    opponent, `teammate=False` marks OUR player — that's the dot being
    mirrored, not `teammate=True`.
    """

    def test_opponent_actor_mirrors_our_dot(self):
        dot = {"location": [100.0, 10.0], "teammate": False, "keeper": False}
        assert _off_ball_dot_xy(dot, actor_is_opponent=True) == (20.0, 70.0)

    def test_own_actor_our_dot_is_unchanged(self):
        dot = {"location": [30.0, 10.0], "teammate": True, "keeper": False}
        assert _off_ball_dot_xy(dot, actor_is_opponent=False) == (30.0, 10.0)

    def test_opponent_actor_opponents_own_dot_is_excluded(self):
        # teammate=True under an opponent actor marks the OPPONENT, not us.
        dot = {"location": [100.0, 10.0], "teammate": True, "keeper": False}
        assert _off_ball_dot_xy(dot, actor_is_opponent=True) is None

    def test_own_actor_opponents_dot_is_excluded(self):
        dot = {"location": [30.0, 10.0], "teammate": False, "keeper": False}
        assert _off_ball_dot_xy(dot, actor_is_opponent=False) is None

    def test_our_keeper_is_excluded_even_though_its_our_dot(self):
        dot = {"location": [30.0, 10.0], "teammate": True, "keeper": True}
        assert _off_ball_dot_xy(dot, actor_is_opponent=False) is None

    def test_our_keeper_is_excluded_under_opponent_actor_too(self):
        dot = {"location": [100.0, 10.0], "teammate": False, "keeper": True}
        assert _off_ball_dot_xy(dot, actor_is_opponent=True) is None


class TestAssertAttacksRight:
    def test_all_right_passes_silently(self):
        _assert_attacks_right({1: "right", 2: "right"}, match_id=1, team="Spain")

    def test_a_left_period_raises(self):
        # StatsBomb coordinates are already attack-right for both teams in
        # both periods (DATA-SPEC-v2 §A) — a "left" result means that
        # assumption has broken for this match, not that a flip is needed.
        with pytest.raises(ValueError, match="non-'right'"):
            _assert_attacks_right({1: "right", 2: "left"}, match_id=1, team="Spain")


def _starting_xi_row(team: str, players: list[str]) -> dict:
    return {
        "team": team, "type": "Starting XI", "minute": 0, "period": 1,
        "tactics": {"lineup": [{"player": {"name": p}} for p in players]},
        "possession_team": None, "location": None, "player": None,
        "play_pattern": None, "player_id": None,
    }


def _touch_row(team: str, player: str, player_id: int, x: float, y: float, minute: int = 10) -> dict:
    return {
        "team": team, "type": "Pass", "minute": minute, "period": 1,
        "tactics": None, "possession_team": team, "location": [x, y],
        "player": player, "play_pattern": "Regular Play", "player_id": player_id,
    }


class TestOnBallPeriodsLaneAndBandCounts:
    def test_counts_sum_to_event_count_and_cover_every_lane_and_band(self):
        # One touch in each lane, one in each band, plus a lane boundary
        # (y=18) and a band boundary (x=120) to exercise the half-open /
        # closed-last-bucket convention end to end (not just lane_for_y /
        # band_for_x in isolation).
        touches = [
            (10.0, 5.0),    # own_third,        left_wing
            (50.0, 20.0),   # own_half,         left_half_space
            (70.0, 40.0),   # opposition_half,  centre
            (90.0, 55.0),   # final_third,      right_half_space
            (100.0, 70.0),  # final_third,      right_wing
            (120.0, 18.0),  # final_third (x=120 boundary), left_half_space (y=18 boundary)
        ]
        events = pd.DataFrame(
            [_starting_xi_row("Spain", ["Player A"])]
            + [_touch_row("Spain", "Player A", 1, x, y) for x, y in touches]
        )
        nicknames = {1: "Player A"}

        periods = _on_ball_periods(events, "Spain", nicknames)

        assert len(periods) == 1
        nodes = periods[0]["nodes"]
        assert len(nodes) == 1
        node = nodes[0]

        assert node["event_count"] == 6
        assert sum(node["lane_counts"].values()) == 6
        assert sum(node["band_counts"].values()) == 6
        assert node["lane_counts"] == {
            "left_wing": 1,
            "left_half_space": 2,  # y=20 and the y=18 boundary
            "centre": 1,
            "right_half_space": 1,
            "right_wing": 1,
        }
        assert node["band_counts"] == {
            "own_third": 1,
            "own_half": 1,
            "opposition_half": 1,
            "final_third": 3,  # x=90, x=100, and the x=120 boundary
        }

    def test_a_coordinate_outside_the_pitch_raises(self):
        # lane_for_y/band_for_x raise on out-of-range input (tested directly
        # in test_tactical_definitions.py); this confirms _on_ball_periods
        # doesn't swallow that and let bad data through silently.
        events = pd.DataFrame(
            [_starting_xi_row("Spain", ["Player A"]),
             _touch_row("Spain", "Player A", 1, 10.0, 81.0)]
        )
        with pytest.raises(ValueError):
            _on_ball_periods(events, "Spain", {1: "Player A"})
