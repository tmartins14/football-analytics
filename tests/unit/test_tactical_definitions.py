"""Unit tests for tactical_definitions. No network calls.

Covers Part 0 (the coordinate edges) and Part 1 (display_minute, thresholds,
claim templates, and the linking-rule term lists) of DATA-SPEC-v2.
"""

import pytest

from statsbomb.tactical_definitions import (
    BANNED_TERMS,
    CAUSAL_TERMS,
    CLAIM_TEMPLATES,
    CONNECTIVES,
    band_for_x,
    display_minute,
    lane_for_y,
)


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


class TestDisplayMinute:
    """DATA-SPEC-v2 Part 1's own test-case list, verbatim."""

    @pytest.mark.parametrize(
        "minute, period, expected",
        [
            (0, 1, "1'"),
            (44, 1, "45'"),
            (45, 1, "45+1'"),
            (47, 1, "45+3'"),
            (45, 2, "46'"),
            (89, 2, "90'"),
            (90, 2, "90+1'"),
        ],
    )
    def test_spec_cases(self, minute, period, expected):
        assert display_minute(minute, period) == expected

    def test_extra_time_raises(self):
        # Extra time is explicitly out of scope for this spec.
        with pytest.raises(ValueError):
            display_minute(95, 3)


class TestClaimTemplates:
    def test_every_table_row_from_the_spec_is_present(self):
        # One entry per row of DATA-SPEC-v2's "Claims" table. team_width and
        # plain `concentration` are deliberately absent — both are
        # value-only findings with no claim in that table.
        assert set(CLAIM_TEMPLATES) == {
            "final_score", "goal", "game_state", "formation", "formation_change",
            "substitution", "role_change", "player_zone", "team_height", "hub",
            "no_hub", "top_pair", "comparison", "change",
        }

    def test_multi_variant_templates_have_their_sub_keys(self):
        assert set(CLAIM_TEMPLATES["final_score"]) == {"win", "draw"}
        assert set(CLAIM_TEMPLATES["game_state"]) == {"leading", "level"}
        assert set(CLAIM_TEMPLATES["player_zone"]) == {"lane", "mixed"}
        assert set(CLAIM_TEMPLATES["team_height"]) == {"own_half", "opposition_half"}
        assert set(CLAIM_TEMPLATES["comparison"]) == {"block_height", "team_height", "concentration"}
        assert set(CLAIM_TEMPLATES["change"]) == {"hub"}

    def test_a_couple_of_templates_render_the_spec_examples(self):
        # "Nico Williams scored for Spain (47')" — the spec's own example.
        rendered = CLAIM_TEMPLATES["goal"].format(player="Nico Williams", team="Spain", display_minute="47'")
        assert rendered == "Nico Williams scored for Spain (47')"

        rendered = CLAIM_TEMPLATES["top_pair"].format(a="Laporte", b="Le Normand", n=31, window="kick-off to 45'")
        assert rendered == "Laporte and Le Normand combined 31 times (kick-off to 45')"

    def test_no_claim_template_contains_a_banned_or_causal_word(self):
        # "No template contains a causal word or a word from the 'Banned
        # everywhere' list" (DATA-SPEC-v2, Claims "Rules").
        for entry in CLAIM_TEMPLATES.values():
            templates = entry.values() if isinstance(entry, dict) else [entry]
            for template in templates:
                lowered = template.lower()
                for term in BANNED_TERMS | CAUSAL_TERMS:
                    assert term not in lowered, f"{term!r} found in template {template!r}"


class TestConnectivesAndTermLists:
    def test_causal_terms_are_all_banned_everywhere_too(self):
        assert CAUSAL_TERMS <= BANNED_TERMS

    def test_joining_and_sequence_connectives_are_disjoint(self):
        assert CONNECTIVES["joining"].isdisjoint(CONNECTIVES["sequence"])
