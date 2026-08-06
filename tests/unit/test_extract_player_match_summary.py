"""Unit tests for extract_player_match_summary's pure per-player aggregation
helpers. No network calls — inputs are hand-built DataFrames shaped like
extract_player_events()'s / sb.events()'s real output.
"""

import pandas as pd
import pytest

from statsbomb.extract_player_match_summary import (
    _duels_won_pct,
    _padj_defensive_actions,
    _possession_shares,
    _pressure_regains,
    _progressive_passes,
    _xa,
    _xg,
    _xg_chain,
)


def _events(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


class TestProgressivePasses:
    def test_counts_only_progressive_passes(self):
        events = _events([
            {"type": "Pass", "is_progressive": True},
            {"type": "Pass", "is_progressive": False},
            {"type": "Carry", "is_progressive": True},  # not a Pass — excluded
        ])
        assert _progressive_passes(events) == 1

    def test_none_values_do_not_count(self):
        events = _events([{"type": "Pass", "is_progressive": None}])
        assert _progressive_passes(events) == 0


class TestPressureRegains:
    def test_counts_only_regaining_pressures(self):
        events = _events([
            {"type": "Pressure", "pressure_regain": True},
            {"type": "Pressure", "pressure_regain": False},
            {"type": "Duel", "pressure_regain": None},
        ])
        assert _pressure_regains(events) == 1


class TestDuelsWonPct:
    def test_mixed_outcomes(self):
        events = _events([
            {"type": "Duel", "outcome": "Won"},
            {"type": "Duel", "outcome": "Success In Play"},
            {"type": "Duel", "outcome": "Lost Out"},
            {"type": "Duel", "outcome": "Lost In Play"},
        ])
        assert _duels_won_pct(events) == 50.0

    def test_no_duels_returns_none(self):
        events = _events([{"type": "Pass", "outcome": None}])
        assert _duels_won_pct(events) is None

    def test_returns_native_float_not_numpy(self):
        events = _events([{"type": "Duel", "outcome": "Won"}])
        result = _duels_won_pct(events)
        assert type(result) is float


class TestXg:
    def test_sums_own_shot_xg(self):
        events = _events([
            {"type": "Shot", "shot_xg": 0.1},
            {"type": "Shot", "shot_xg": 0.25},
            {"type": "Pass", "shot_xg": None},
        ])
        assert _xg(events) == 0.35

    def test_no_shots_returns_zero(self):
        events = _events([{"type": "Pass", "shot_xg": None}])
        assert _xg(events) == 0.0


class TestXa:
    def test_sums_xg_of_assisted_shots(self):
        match_events = _events([
            {"id": "pass-1", "player_id": 10, "type": "Pass", "pass_assisted_shot_id": "shot-1"},
            {"id": "shot-1", "player_id": 20, "type": "Shot", "shot_statsbomb_xg": 0.4},
        ])
        assert _xa(match_events, player_id=10) == 0.4

    def test_no_assists_returns_zero(self):
        match_events = _events([
            {"id": "pass-1", "player_id": 10, "type": "Pass", "pass_assisted_shot_id": None},
        ])
        assert _xa(match_events, player_id=10) == 0.0


class TestXgChain:
    def test_sums_shot_xg_across_touched_possessions_once_each(self):
        match_events = _events([
            {"player_id": 10, "possession": 1, "type": "Pass"},
            {"player_id": 10, "possession": 1, "type": "Carry"},  # same possession — not double counted
            {"player_id": 99, "possession": 1, "type": "Shot", "shot_statsbomb_xg": 0.3},
            {"player_id": 10, "possession": 2, "type": "Pass"},
            {"player_id": 88, "possession": 2, "type": "Shot", "shot_statsbomb_xg": 0.2},
        ])
        assert _xg_chain(match_events, player_id=10) == 0.5

    def test_untouched_possession_not_counted(self):
        match_events = _events([
            {"player_id": 10, "possession": 1, "type": "Pass"},
            {"player_id": 99, "possession": 2, "type": "Shot", "shot_statsbomb_xg": 0.3},
        ])
        assert _xg_chain(match_events, player_id=10) == 0.0


class TestPossessionShares:
    def test_splits_by_possession_team_of_distinct_possessions(self):
        match_events = _events([
            {"possession": 1, "possession_team": "Spain"},
            {"possession": 1, "possession_team": "Spain"},  # same possession — counted once
            {"possession": 2, "possession_team": "England"},
            {"possession": 3, "possession_team": "Spain"},
        ])
        team_pct, opp_pct = _possession_shares(match_events, "Spain")
        assert team_pct == pytest.approx(66.67, abs=0.01)
        assert opp_pct == pytest.approx(33.33, abs=0.01)


class TestPadjDefensiveActions:
    def test_scales_up_when_opponent_had_more_possession(self):
        events = _events([{"type": "Pressure"}, {"type": "Duel"}, {"type": "Pass"}])
        # opponent had 100% possession -> scaled up 2x relative to the 50% baseline
        assert _padj_defensive_actions(events, opponent_possession_pct=100.0) == 1.0
        assert _padj_defensive_actions(events, opponent_possession_pct=25.0) == 4.0

    def test_zero_opponent_possession_does_not_divide_by_zero(self):
        events = _events([{"type": "Pressure"}])
        # clamped to a 1% floor rather than raising
        result = _padj_defensive_actions(events, opponent_possession_pct=0.0)
        assert result == 50.0
