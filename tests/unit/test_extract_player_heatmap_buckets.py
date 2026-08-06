"""Unit tests for extract_player_heatmap_buckets's pure bucket-boundary helper.

No network calls — compute_kde_grid itself is exercised via the integration
test, since it needs real located events to be meaningful.
"""

from statsbomb.extract_player_heatmap_buckets import _bucket_minutes


class TestBucketMinutes:
    def test_evenly_divisible_max_minute(self):
        assert _bucket_minutes(20, bucket_size=5) == [5, 10, 15, 20]

    def test_non_divisible_max_minute_appends_final_partial_bucket(self):
        assert _bucket_minutes(23, bucket_size=5) == [5, 10, 15, 20, 23]

    def test_max_minute_below_one_bucket_size(self):
        assert _bucket_minutes(3, bucket_size=5) == [3]

    def test_max_minute_zero_returns_empty(self):
        assert _bucket_minutes(0, bucket_size=5) == []

    def test_max_minute_exactly_one_bucket(self):
        assert _bucket_minutes(5, bucket_size=5) == [5]

    def test_custom_bucket_size(self):
        assert _bucket_minutes(22, bucket_size=10) == [10, 20, 22]
