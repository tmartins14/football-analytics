"""Integration test: derive_tactical_findings() against the real Euro 2024
Final (match 3943043) — DATA-SPEC-v2's own "->" example values and every
rendered claim named in its "Claims" table.

These are **regression fixtures**: they prove the code matches this spec,
not that the thresholds are right for football (DATA-SPEC-v2's definitions
are explicitly provisional, calibrated on this one match — decision 11).
Tyler hand-checked these values and claims once against the committed JSON
in `data/euro-2024/3943043/`; from here on, a failure here means the code
changed, not that the spec's own example values were re-derived.

No network call — derive_tactical_findings() reads only the already-
committed extractor JSON in that directory, same as every file it reads.
Still placed in tests/integration/ (and marked accordingly) because it
validates against the one real match's real data, the same category as
every other file in this directory, not synthetic fixtures.
"""

from pathlib import Path

import pytest

from statsbomb import derive_tactical_findings

pytestmark = pytest.mark.integration

DATA_DIR = Path(__file__).parents[2] / "data" / "euro-2024" / "3943043"


@pytest.fixture(scope="module")
def result(match_id):
    return derive_tactical_findings(match_id, DATA_DIR)


@pytest.fixture(scope="module")
def findings(result):
    return result["findings"]


@pytest.fixture(scope="module")
def suppressed(result):
    return result["suppressed"]


def _find(findings, type_, **kw):
    return [f for f in findings if f["type"] == type_ and all(f.get(k) == v for k, v in kw.items())]


def _find1(findings, type_, **kw):
    rows = _find(findings, type_, **kw)
    assert len(rows) == 1, f"expected exactly 1 {type_} with {kw}, got {len(rows)}"
    return rows[0]


class TestContext:
    def test_final_score(self, findings):
        fs = _find1(findings, "final_score")
        assert fs["value"] == {"home_score": 2, "away_score": 1}
        assert fs["claim"] == "Spain beat England 2–1"

    def test_three_goals(self, findings):
        goals = {g["evidence"]["minute"]: g for g in _find(findings, "goal")}
        assert set(goals) == {46, 72, 85}
        assert goals[46]["claim"] == "Nico Williams scored for Spain (47')"
        assert goals[72]["claim"] == "Cole Palmer scored for England (73')"
        assert goals[85]["claim"] == "Mikel Oyarzabal scored for Spain (86')"

    def test_game_state_segments(self, findings):
        segments = sorted(_find(findings, "game_state"), key=lambda f: f["window"]["index"])
        assert [(s["team"], s["label"]) for s in segments] == [
            (None, "level"), ("Spain", "leading"), (None, "level"), ("Spain", "leading"),
        ]
        assert [s["claim"] for s in segments] == [
            "the score was level at 0-0 from kick-off to 47'",
            "Spain led 1-0 from 47' to 73'",
            "the score was level at 1-1 from 73' to 86'",
            "Spain led 2-1 from 86' to full time",
        ]


class TestStructure:
    def test_formation_periods(self, findings):
        assert len(_find(findings, "formation", team="England")) == 3
        assert len(_find(findings, "formation", team="Spain")) == 2

    def test_formation_change_england_only(self, findings):
        changes = _find(findings, "formation_change")
        assert len(changes) == 1
        assert changes[0]["team"] == "England"
        assert changes[0]["value"] == {"old": "4-2-3-1", "new": "4-1-2-1-2"}
        assert changes[0]["claim"] == "England changed from a 4-2-3-1 to a 4-1-2-1-2 (90')"

    def test_role_changes(self, findings):
        eng = _find(findings, "role_change", team="England")
        esp = _find(findings, "role_change", team="Spain")
        at_69 = {f["subject"]["display_name"] for f in eng if f["evidence"]["minute"] == 69}
        at_89_eng = {f["subject"]["display_name"] for f in eng if f["evidence"]["minute"] == 89}
        at_89_esp = {f["subject"]["display_name"] for f in esp if f["evidence"]["minute"] == 89}
        assert at_69 == {"Jude Bellingham", "Phil Foden"}
        assert at_89_eng == {"Declan Rice", "Bukayo Saka", "Jude Bellingham", "Ollie Watkins"}
        assert at_89_esp == {"Daniel Olmo"}
        bellingham_69 = next(f for f in eng if f["subject"]["display_name"] == "Jude Bellingham" and f["evidence"]["minute"] == 69)
        assert bellingham_69["claim"] == "Jude Bellingham moved from Left Wing to Right Defensive Midfield (70')"

    def test_substitute_counts(self, findings):
        assert len(_find(findings, "substitution", team="England")) == 3
        assert len(_find(findings, "substitution", team="Spain")) == 4

    def test_substitution_claim(self, findings):
        palmer = next(f for f in _find(findings, "substitution", team="England") if f["subject"]["display_name"] == "Cole Palmer")
        assert palmer["claim"] == "Cole Palmer replaced Kobbie Mainoo for England (70')"


class TestShapeInPossession:
    def test_yamal_h1_right_wing(self, findings):
        yamal = next(
            f for f in _find(findings, "player_zone", team="Spain")
            if "Yamal" in f["subject"]["display_name"] and f["window"]["index"] == 0
        )
        assert yamal["label"] == "right_wing"
        assert yamal["claim"] == "Lamine Yamal took 29 of 40 touches on the right wing (kick-off to 46')"

    def test_williams_h1_mixed(self, findings):
        williams = next(
            f for f in _find(findings, "player_zone", team="Spain")
            if "Williams" in f["subject"]["display_name"] and f["window"]["index"] == 0
        )
        assert williams["label"] == "mixed"
        assert williams["claim"] == "Nico Williams split touches between the left wing (20) and the left half-space (15) (kick-off to 46')"

    def test_team_height(self, findings):
        esp = next(f for f in _find(findings, "team_height", team="Spain") if f["window"]["index"] == 0)
        eng = next(f for f in _find(findings, "team_height", team="England") if f["window"]["index"] == 0)
        assert esp["value"] == pytest.approx(65.9, abs=0.1)
        assert esp["label"] == "opposition_half"
        assert eng["value"] == pytest.approx(59.5, abs=0.1)
        assert eng["label"] == "own_half"

    def test_team_width(self, findings):
        esp = next(f for f in _find(findings, "team_width", team="Spain") if f["window"]["index"] == 0)
        eng = next(f for f in _find(findings, "team_width", team="England") if f["window"]["index"] == 0)
        assert esp["value"] == pytest.approx(60.8, abs=0.1)
        assert eng["value"] == pytest.approx(59.8, abs=0.1)

    def test_only_first_window_emits_team_level_findings(self, suppressed):
        # "Consequence on this match: only the first window of each team
        # emits team-level findings" -- every later window is suppressed.
        later_windows = [s for s in suppressed if s["type"] in ("team_height", "team_width") and s["window"]["index"] > 0]
        assert len(later_windows) > 0
        assert all(s["reason"] == "MIN_ELIGIBLE_OUTFIELD" for s in later_windows)


class TestShapeOutOfPossession:
    def test_block_height(self, findings):
        esp = _find1(findings, "block_height", team="Spain")
        eng = _find1(findings, "block_height", team="England")
        assert esp["value"] == 55.05
        assert eng["value"] == 45.98


class TestPassingStructure:
    def test_spain_window0_hubs(self, findings):
        hubs = {f["subject"]["display_name"] for f in _find(findings, "hub", team="Spain") if f["window"]["index"] == 0}
        assert hubs == {"Aymeric Laporte", "Robin Le Normand"}
        laporte = next(f for f in _find(findings, "hub", team="Spain") if f["subject"]["display_name"] == "Aymeric Laporte" and f["window"]["index"] == 0)
        le_normand = next(f for f in _find(findings, "hub", team="Spain") if f["subject"]["display_name"] == "Robin Le Normand" and f["window"]["index"] == 0)
        assert laporte["claim"] == "Aymeric Laporte was a hub for Spain, involved in 16.4% of passes (kick-off to 46')"
        assert le_normand["claim"] == "Robin Le Normand was a hub for Spain, involved in 16.5% of passes (kick-off to 46')"

    def test_spain_window2_hubs(self, findings):
        hubs = {f["subject"]["display_name"] for f in _find(findings, "hub", team="Spain") if f["window"]["index"] == 2}
        assert hubs == {"Aymeric Laporte", "Robin Le Normand"}

    def test_spain_window1_and_england_window0_have_no_hub(self, findings):
        assert [f for f in _find(findings, "hub", team="Spain") if f["window"]["index"] == 1] == []
        assert [f for f in _find(findings, "hub", team="England") if f["window"]["index"] == 0] == []
        spain_no_hub = next(f for f in _find(findings, "no_hub", team="Spain") if f["window"]["index"] == 1)
        england_no_hub = next(f for f in _find(findings, "no_hub", team="England") if f["window"]["index"] == 0)
        assert spain_no_hub["claim"] == "Spain's passing had no single hub; the most involved player, Fabián Ruiz, had 14.3% (46' to 68')"
        assert england_no_hub["claim"] == "England's passing had no single hub; the most involved player, John Stones, had 12.8% (kick-off to 61')"

    def test_spain_window0_top_pairs_include_the_tie(self, findings):
        pairs = {tuple(sorted(f["subject"]["pair"])): f["value"] for f in _find(findings, "top_pair", team="Spain") if f["window"]["index"] == 0}
        assert pairs == {
            tuple(sorted(["Aymeric Laporte", "Robin Le Normand"])): 31,
            tuple(sorted(["Robin Le Normand", "Daniel Carvajal"])): 23,
            tuple(sorted(["Aymeric Laporte", "Marc Cucurella"])): 16,
            tuple(sorted(["Aymeric Laporte", "Rodri"])): 16,
        }

    def test_england_window0_top_pairs(self, findings):
        pairs = {tuple(sorted(f["subject"]["pair"])): f["value"] for f in _find(findings, "top_pair", team="England") if f["window"]["index"] == 0}
        assert pairs == {
            tuple(sorted(["John Stones", "Jordan Pickford"])): 13,
            tuple(sorted(["Declan Rice", "Jude Bellingham"])): 11,
            tuple(sorted(["John Stones", "Kyle Walker"])): 10,
        }

    def test_concentration(self, findings):
        esp = next(f for f in _find(findings, "concentration", team="Spain") if f["window"]["index"] == 0)
        eng = next(f for f in _find(findings, "concentration", team="England") if f["window"]["index"] == 0)
        assert esp["value"] * 100 == pytest.approx(44.8, abs=0.1)
        assert eng["value"] * 100 == pytest.approx(37.0, abs=0.1)

    def test_suppressed_short_windows(self, suppressed):
        eng = {(s["window"]["text"], s["detail"]["window_passes"]) for s in suppressed if s["team"] == "England" and s["reason"] == "MIN_WINDOW_PASSES"}
        esp = {(s["window"]["text"], s["detail"]["window_passes"]) for s in suppressed if s["team"] == "Spain" and s["reason"] == "MIN_WINDOW_PASSES"}
        assert eng == {("61' to 70'", 28), ("70' to 90'", 38), ("90' to full time", 4)}
        assert esp == {("83' to 89'", 30), ("89' to full time", 1)}


class TestCrossCutting:
    def test_block_height_comparison(self, findings):
        comp = _find1(findings, "comparison", team="England")
        assert comp["id"] == "cross.comparison.block_height.ENG"
        assert comp["value"] == pytest.approx(9.1, abs=0.1)
        assert comp["claim"] == "England's average out-of-possession position was 9.1 yards deeper than Spain's"

    def test_team_height_comparison(self, findings):
        comp = next(f for f in _find(findings, "comparison", team="Spain") if f["id"].startswith("cross.comparison.team_height"))
        assert comp["value"] == pytest.approx(6.4, abs=0.1)
        assert comp["claim"] == "Spain's average position in possession was 6.4 yards higher than England's (Spain kick-off to 46', England kick-off to 61')"

    def test_team_width_comparison_not_emitted(self, suppressed):
        assert any(s["id"] == "cross.comparison.team_width" and s["reason"] == "COMPARE_MIN_YARDS" for s in suppressed)

    def test_concentration_comparison(self, findings):
        comp = next(f for f in _find(findings, "comparison", team="Spain") if f["id"].startswith("cross.comparison.concentration"))
        assert comp["value"] == pytest.approx(7.8, abs=0.3)
        assert comp["claim"] == "Spain's passing was more concentrated than England's: the top three players had 44.8% of involvement against 37.0% (kick-off to 46')"

    def test_no_hub_change_on_this_match(self, findings):
        # "Laporte 16.4% -> 12.6% is a 3.8-point move" -- below CHANGE_MIN_SHARE (4 points).
        assert _find(findings, "change") == []


class TestDeterminism:
    def test_two_runs_produce_identical_output(self, result, match_id):
        rerun = derive_tactical_findings(match_id, DATA_DIR)
        assert rerun == result
