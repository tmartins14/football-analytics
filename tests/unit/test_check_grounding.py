"""Unit tests for check_grounding() — DATA-SPEC-v2 Part 4 step 6.

Hand-written sentences built from match 3943043's real findings (read from
the committed data/euro-2024/3943043/tactical_findings.json, no network),
covering the spec's exact must-fail / must-pass list. check_grounding()
itself makes no API call — it's a pure function over sentences + findings.
"""

import json
from pathlib import Path

import pytest

from ai.match_summary.generate_match_summary import check_grounding

FINDINGS = json.loads(
    (Path(__file__).parents[2] / "data" / "euro-2024" / "3943043" / "tactical_findings.json").read_text()
)["findings"]

WILLIAMS_GOAL = "context.goal.ESP.nico_williams"
PALMER_GOAL = "context.goal.ENG.cole_palmer"
LAPORTE_HUB = "passing.hub.ESP.w0.aymeric_laporte"
LE_NORMAND_HUB = "passing.hub.ESP.w0.robin_le_normand"
BELLINGHAM_ROLE_CHANGE = "structure.role_change.ENG.jude_bellingham.p1"
BLOCK_HEIGHT_COMPARISON = "cross.comparison.block_height.ENG"
CONCENTRATION_COMPARISON = "cross.comparison.concentration.ESP"
PALMER_SUBSTITUTION = "structure.substitution.ENG.cole_palmer"


def _report_for(text: str, finding_ids: list[str]) -> dict:
    report = check_grounding([{"text": text, "finding_ids": finding_ids}], FINDINGS)
    return report["sentences"][0]


class TestMustFail:
    def test_reversed_comparison(self):
        # The spec's own example: the real claim says England is deeper.
        sentence = _report_for(
            "Spain's average out-of-possession position was 9.1 yards deeper than England's",
            [BLOCK_HEIGHT_COMPARISON],
        )
        assert sentence["passed"] is False
        assert sentence["checks"]["claims_present"] is False

    def test_swapped_hub_numbers(self):
        sentence = _report_for(
            "Aymeric Laporte was a hub for Spain, involved in 16.5% of passes (kick-off to 46') and "
            "Robin Le Normand was a hub for Spain, involved in 16.4% of passes (kick-off to 46')",
            [LAPORTE_HUB, LE_NORMAND_HUB],
        )
        assert sentence["passed"] is False
        assert sentence["checks"]["claims_present"] is False

    def test_reversed_role_change(self):
        sentence = _report_for(
            "Jude Bellingham moved from Right Defensive Midfield to Left Wing (70')",
            [BELLINGHAM_ROLE_CHANGE],
        )
        assert sentence["passed"] is False
        assert sentence["checks"]["claims_present"] is False

    def test_causal_word_between_two_valid_claims(self):
        sentence = _report_for(
            "Nico Williams scored for Spain (47') because Cole Palmer scored for England (73')",
            [WILLIAMS_GOAL, PALMER_GOAL],
        )
        assert sentence["passed"] is False
        assert sentence["checks"]["leftover_clean"] is False
        assert sentence["checks"]["no_banned_terms"] is False

    def test_wrong_minute(self):
        # Palmer's real claim renders display_minute(72, 2) == "73'".
        sentence = _report_for("Cole Palmer scored for England (72')", [PALMER_GOAL])
        assert sentence["passed"] is False
        assert sentence["checks"]["claims_present"] is False

    def test_player_name_in_leftover(self):
        sentence = _report_for("Nico Williams scored for Spain (47'), as Rodri assisted", [WILLIAMS_GOAL])
        assert sentence["passed"] is False
        assert sentence["checks"]["leftover_clean"] is False

    def test_digit_in_leftover(self):
        sentence = _report_for("Nico Williams scored for Spain (47') in the 50th minute", [WILLIAMS_GOAL])
        assert sentence["passed"] is False
        assert sentence["checks"]["leftover_clean"] is False

    def test_sequence_word_with_no_minute_bearing_finding_cited(self):
        sentence = _report_for(
            "England's average out-of-possession position was 9.1 yards deeper than Spain's then "
            "Spain's passing was more concentrated than England's: the top three players had 44.8% "
            "of involvement against 37.0% (kick-off to 46')",
            [BLOCK_HEIGHT_COMPARISON, CONCENTRATION_COMPARISON],
        )
        assert sentence["passed"] is False
        assert sentence["checks"]["sequence_requires_minute_bearing"] is False
        # Both cited findings are "comparison" type -- neither is minute-bearing.
        assert sentence["checks"]["leftover_clean"] is True

    def test_a_cited_id_whose_claim_is_absent_from_the_text(self):
        # Palmer's goal is cited but never actually stated in the text.
        sentence = _report_for("Nico Williams scored for Spain (47')", [WILLIAMS_GOAL, PALMER_GOAL])
        assert sentence["passed"] is False
        assert sentence["checks"]["claims_present"] is False
        assert sentence["missing_claim_ids"] == [PALMER_GOAL]

    def test_an_unknown_id(self):
        sentence = _report_for("Nico Williams scored for Spain (47')", [WILLIAMS_GOAL, "unknown.finding.id"])
        assert sentence["passed"] is False
        assert sentence["checks"]["cites_valid_ids"] is False
        assert sentence["unknown_ids"] == ["unknown.finding.id"]


class TestMustPass:
    def test_a_claim_opening_a_sentence(self):
        sentence = _report_for("Nico Williams scored for Spain (47')", [WILLIAMS_GOAL])
        assert sentence["passed"] is True

    def test_a_claim_after_a_connective(self):
        # "cole" (lowercase c) exercises the first-character-case-insensitive rule.
        sentence = _report_for(
            "Nico Williams scored for Spain (47') and cole Palmer scored for England (73')",
            [WILLIAMS_GOAL, PALMER_GOAL],
        )
        assert sentence["passed"] is True

    def test_two_claims_joined_by_and(self):
        sentence = _report_for(
            "Nico Williams scored for Spain (47') and Cole Palmer scored for England (73')",
            [WILLIAMS_GOAL, PALMER_GOAL],
        )
        assert sentence["passed"] is True

    def test_two_claims_joined_by_while(self):
        sentence = _report_for(
            "Nico Williams scored for Spain (47') while Cole Palmer scored for England (73')",
            [WILLIAMS_GOAL, PALMER_GOAL],
        )
        assert sentence["passed"] is True

    def test_after_with_a_substitution_cited(self):
        sentence = _report_for(
            "after Cole Palmer replaced Kobbie Mainoo for England (70'), "
            "Jude Bellingham moved from Left Wing to Right Defensive Midfield (70')",
            [PALMER_SUBSTITUTION, BELLINGHAM_ROLE_CHANGE],
        )
        assert sentence["passed"] is True
