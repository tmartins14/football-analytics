"""Integration test: DATA-SPEC-v3 Part 1's four tier-1 extractors against
the real Euro 2024 Final (match 3943043).

Every asserted value below was independently recomputed by hand against raw
`sb.events()` output with ad hoc pandas filters written separately from the
extractor modules themselves (not just re-running the extractor and
comparing to its own output) — the bar DATA-SPEC.md sets ("PPDA matches an
independent manual recount over a sample window") and the one v2 used for
`team_shape`'s centroid. Spain's progressive-action total (43) and England's
(25) were additionally cross-checked against the pre-existing, independently
authored `extract_progressive_map` extractor's own `progressive` column sum
for the same match — a second, structurally different source agreeing
exactly.

No suppression thresholds or tercile labels are asserted here — Part 1
extractors emit raw values only; labeling is Part 4's job once reference
data exists (DATA-SPEC-v3's Build section).
"""

import pytest

from statsbomb.extract_chance_creation import extract_chance_creation
from statsbomb.extract_defending import extract_defending
from statsbomb.extract_pressing import extract_pressing
from statsbomb.extract_progression import extract_progression

pytestmark = pytest.mark.integration


class TestChanceCreation:
    def test_spain_non_penalty_shots_and_npxg(self, match_id):
        result = extract_chance_creation(match_id, "Spain")
        assert result["shots"]["non_penalty_count"] == 16
        assert result["shots"]["total_npxg"] == pytest.approx(1.791713, abs=1e-5)

    def test_england_non_penalty_shots_and_npxg(self, match_id):
        result = extract_chance_creation(match_id, "England")
        assert result["shots"]["non_penalty_count"] == 9
        assert result["shots"]["total_npxg"] == pytest.approx(0.726378, abs=1e-5)

    def test_zone_and_source_counts_foot_to_the_shot_total(self, match_id):
        # Independent internal-consistency check: every shot lands in
        # exactly one zone and exactly one source bucket.
        result = extract_chance_creation(match_id, "Spain")
        zone_count = sum(z["count"] for z in result["shots"]["by_zone"].values())
        source_count = sum(s["count"] for s in result["shots"]["by_source"].values())
        assert zone_count == result["shots"]["non_penalty_count"]
        assert source_count == result["shots"]["non_penalty_count"]

    def test_top_creator_is_lamine_yamal(self, match_id):
        result = extract_chance_creation(match_id, "Spain")
        top = result["creators"][0]
        assert top["display_name"] == "Lamine Yamal"
        assert top["xa"] == pytest.approx(0.382136, abs=1e-5)
        assert top["key_passes"] == 3


class TestProgression:
    def test_spain_progressive_action_total(self, match_id):
        # Cross-checked against extract_progressive_map's own independent total.
        result = extract_progression(match_id, "Spain")
        assert result["progressive_actions"]["total_count"] == 43
        assert result["progressive_actions"]["by_mode"] == {"pass": 31, "carry": 12}

    def test_england_progressive_action_total(self, match_id):
        result = extract_progression(match_id, "England")
        assert result["progressive_actions"]["total_count"] == 25

    def test_side_counts_foot_to_the_total(self, match_id):
        result = extract_progression(match_id, "Spain")
        by_side = result["progressive_actions"]["by_side"]
        assert sum(by_side.values()) == result["progressive_actions"]["total_count"]


class TestPressing:
    def test_spain_ppda(self, match_id):
        result = extract_pressing(match_id)
        ppda = result["teams"]["Spain"]["ppda"]
        assert ppda["opponent_passes_attempted_deep"] == 77
        assert ppda["defensive_actions_advanced"] == 20
        assert ppda["value"] == pytest.approx(3.85, abs=1e-3)

    def test_england_ppda(self, match_id):
        result = extract_pressing(match_id)
        ppda = result["teams"]["England"]["ppda"]
        assert ppda["opponent_passes_attempted_deep"] == 134
        assert ppda["defensive_actions_advanced"] == 17
        assert ppda["value"] == pytest.approx(7.8824, abs=1e-3)

    def test_spain_pressed_more_intensely_than_england(self, match_id):
        # Lower PPDA = more intense (DATA-SPEC-v3 Q4). Matches this final's
        # well-documented tactical story (Spain's high press), an
        # independent plausibility check beyond the raw recount above.
        result = extract_pressing(match_id)
        assert result["teams"]["Spain"]["ppda"]["value"] < result["teams"]["England"]["ppda"]["value"]

    def test_pressure_received_covers_every_eligible_outfield_player(self, match_id):
        result = extract_pressing(match_id)
        teams = {p["team"] for p in result["pressure_received"]}
        assert teams == {"Spain", "England"}
        assert len(result["pressure_received"]) > 20  # both squads, subs included, GKs excluded

    def test_jude_bellingham_pressure_received(self, match_id):
        # A meaningful-volume entry (124 credited events), not the 1-event
        # edge case that happens to sort to the top.
        result = extract_pressing(match_id)
        bellingham = next(
            p for p in result["pressure_received"] if p["display_name"] == "Jude Bellingham"
        )
        assert bellingham["team"] == "England"
        assert bellingham["on_ball_events"] == 124
        assert bellingham["under_pressure_events"] == 56


class TestDefending:
    def test_spain_defensive_action_height(self, match_id):
        result = extract_defending(match_id, "Spain")
        assert result["defensive_action_height"]["n_actions"] == 85
        assert result["defensive_action_height"]["mean_x"] == pytest.approx(46.52, abs=0.01)

    def test_spain_win_zone_foots_to_an_independent_recount(self, match_id):
        # Independently recounted: 39 Ball Recovery/Interception + 10
        # successful Tackles = 49.
        result = extract_defending(match_id, "Spain")
        assert sum(result["win_zone"].values()) == 49

    def test_spain_high_turnovers(self, match_id):
        result = extract_defending(match_id, "Spain")
        assert result["high_turnovers"] == {"count": 4, "ended_in_shot": 2}

    def test_england_high_turnovers(self, match_id):
        result = extract_defending(match_id, "England")
        assert result["high_turnovers"] == {"count": 1, "ended_in_shot": 1}
