"""Unit tests for reference_distributions' tercile math. No network calls.

Covers DATA-SPEC-v3 Part 2's own acceptance bar: tercile labelling on a
synthetic distribution, including a value exactly on a cut point ("lower
tercile owns the cut").
"""

import pytest

from statsbomb.reference_distributions import tercile_cutpoints, tercile_label


class TestTercileCutpoints:
    def test_nine_values_splits_into_three_even_thirds(self):
        values = [9, 1, 5, 3, 7, 2, 8, 4, 6]  # 1..9, unsorted on purpose
        cut_low, cut_high = tercile_cutpoints(values)
        assert cut_low == 3
        assert cut_high == 6

    def test_remainder_is_absorbed_into_the_top_third(self):
        # n=10, k=3: bottom/middle thirds get 3 each (indices 0-2, 3-5),
        # the remaining 4 values (indices 6-9) all fall in the top third.
        values = list(range(1, 11))  # 1..10
        cut_low, cut_high = tercile_cutpoints(values)
        assert cut_low == 3
        assert cut_high == 6

    def test_fewer_than_three_values_raises(self):
        with pytest.raises(ValueError):
            tercile_cutpoints([1, 2])


class TestTercileLabel:
    def test_value_below_cut_low_is_bottom_third(self):
        assert tercile_label(2, cut_low=3, cut_high=6) == "bottom_third"

    def test_value_exactly_on_cut_low_is_bottom_third(self):
        # "Lower tercile owns the cut" — the boundary value belongs to the
        # third it's the *top* of, not the one above it.
        assert tercile_label(3, cut_low=3, cut_high=6) == "bottom_third"

    def test_value_between_cuts_is_middle_third(self):
        assert tercile_label(5, cut_low=3, cut_high=6) == "middle_third"

    def test_value_exactly_on_cut_high_is_middle_third(self):
        assert tercile_label(6, cut_low=3, cut_high=6) == "middle_third"

    def test_value_above_cut_high_is_top_third(self):
        assert tercile_label(7, cut_low=3, cut_high=6) == "top_third"

    def test_end_to_end_with_remainder_distribution(self):
        values = list(range(1, 11))
        cut_low, cut_high = tercile_cutpoints(values)
        labels = [tercile_label(v, cut_low, cut_high) for v in values]
        assert labels == [
            "bottom_third", "bottom_third", "bottom_third",
            "middle_third", "middle_third", "middle_third",
            "top_third", "top_third", "top_third", "top_third",
        ]
