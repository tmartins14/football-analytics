"""Unit tests for extract_possession_shares's pure helpers. No network calls."""

import pandas as pd

from statsbomb.extract_possession_shares import _bucket_minutes, _possession_shares_at


class TestBucketMinutes:
    def test_evenly_divisible_max_minute(self):
        assert _bucket_minutes(20, bucket_size=5) == [5, 10, 15, 20]

    def test_non_divisible_max_minute_appends_final_partial_bucket(self):
        assert _bucket_minutes(23, bucket_size=5) == [5, 10, 15, 20, 23]

    def test_max_minute_below_one_bucket_size(self):
        assert _bucket_minutes(3, bucket_size=5) == [3]

    def test_max_minute_zero_returns_empty(self):
        assert _bucket_minutes(0, bucket_size=5) == []


class TestPossessionSharesAt:
    def _events(self, rows):
        return pd.DataFrame(rows)

    def test_splits_by_possession_team_of_distinct_possessions(self):
        events = self._events([
            {"minute": 1, "possession": 1, "possession_team": "Spain"},
            {"minute": 2, "possession": 1, "possession_team": "Spain"},  # same possession — counted once
            {"minute": 3, "possession": 2, "possession_team": "England"},
            {"minute": 4, "possession": 3, "possession_team": "Spain"},
        ])
        shares = _possession_shares_at(events, upto_minute=10, teams=["England", "Spain"])
        assert shares["Spain"] == 66.67
        assert shares["England"] == 33.33

    def test_respects_the_minute_cutoff(self):
        events = self._events([
            {"minute": 1, "possession": 1, "possession_team": "Spain"},
            {"minute": 20, "possession": 2, "possession_team": "England"},
        ])
        shares = _possession_shares_at(events, upto_minute=5, teams=["England", "Spain"])
        assert shares["Spain"] == 100.0
        assert shares["England"] == 0.0

    def test_both_teams_present_even_with_zero_possessions_so_far(self):
        events = self._events([{"minute": 50, "possession": 1, "possession_team": "Spain"}])
        shares = _possession_shares_at(events, upto_minute=1, teams=["England", "Spain"])
        assert shares == {"England": 0.0, "Spain": 0.0}
