"""Unit tests for derive_tactical_findings's category-building functions.

Synthetic data only, no files and no network — each private category
function (`_context_findings`, `_structure_findings`, etc.) takes already-
parsed dicts shaped like the real extractor JSON, so a test can construct
exactly the edge case it needs directly in Python, following the same
synthetic-data convention established in test_extract_substitutes.py /
test_extract_team_shape.py.

Covers DATA-SPEC-v2 Part 3's unit-test list: every threshold edge (a hub
share of exactly HUB_SHARE, a window of exactly MIN_WINDOW_PASSES, a tie at
the top_pair cut, a `mixed` player_zone lane) plus one rendered claim per
`CLAIM_TEMPLATES` entry.
"""

from statsbomb.derive_tactical_findings import (
    _context_findings,
    _cross_cutting_findings,
    _in_possession_findings,
    _passing_findings,
    _structure_findings,
)


# ---------------------------------------------------------------------------
# Synthetic-fixture builders, matching the real extractor JSON shapes.
# ---------------------------------------------------------------------------

def _match_stats(home, away, home_score, away_score):
    return {"home": {"team": home, "score": home_score}, "away": {"team": away, "score": away_score}}


def _shot(team, display_name, minute, period, is_goal=True):
    return {"team": team, "display_name": display_name, "minute": minute, "period": period, "is_goal": is_goal}


def _formation_player(player_id, player, display_name, position):
    return {
        "player_id": player_id, "player": player, "display_name": display_name,
        "position": position, "jersey_number": 1, "template_x": 60.0, "template_y": 40.0,
    }


def _formation_period(formation, from_minute, from_period, to_minute, to_period, players):
    return {
        "formation": formation, "from_minute": from_minute, "from_period": from_period,
        "to_minute": to_minute, "to_period": to_period, "players": players,
    }


def _formation_team(periods):
    return {"periods": periods}


def _substitute(player, display_name, on_minute, on_period, replaced_player, position="Right Wing"):
    return {
        "player": player, "display_name": display_name, "jersey_number": 20, "position": position,
        "on_minute": on_minute, "on_second": 0, "on_period": on_period, "replaced_player": replaced_player,
    }


_ZERO_LANE_COUNTS = {"left_wing": 0, "left_half_space": 0, "centre": 0, "right_half_space": 0, "right_wing": 0}
_ZERO_BAND_COUNTS = {"own_third": 0, "own_half": 0, "opposition_half": 0, "final_third": 0}


def _on_ball_node(player_id, player, display_name, x, y, event_count, lane_counts, band_counts=None):
    return {
        "player_id": player_id, "player": player, "display_name": display_name,
        "x": x, "y": y, "event_count": event_count,
        "lane_counts": lane_counts, "band_counts": band_counts or dict(_ZERO_BAND_COUNTS),
    }


def _on_ball_period(from_minute, from_period, to_minute, to_period, nodes):
    return {"from_minute": from_minute, "from_period": from_period, "to_minute": to_minute, "to_period": to_period, "nodes": nodes}


def _team_shape_team(on_ball_periods):
    return {"on_ball": {"periods": on_ball_periods}}


def _pn_node(player, display_name, passes):
    return {"player": player, "display_name": display_name, "x": 50.0, "y": 40.0, "passes": passes}


def _pn_window(index, from_minute, from_period, to_minute, to_period, nodes, edges):
    return {
        "index": index, "label": f"w{index}", "from_minute": from_minute, "from_period": from_period,
        "to_minute": to_minute, "to_period": to_period, "nodes": nodes, "edges": edges,
    }


def _fake_finding(type_, team, value, *, window=None, subject=None):
    """A minimal finding dict, for feeding _cross_cutting_findings directly
    without going through a whole base category.
    """
    return {
        "id": "test", "category": "test", "type": type_, "team": team, "window": window,
        "game_states": [], "subject": subject, "label": None, "value": value, "claim": None,
        "evidence": {}, "threshold": None, "notability": 1.0, "definitions_version": "0.1.0",
    }


# ---------------------------------------------------------------------------
# Context: final_score (win/draw), goal, game_state (level/leading)
# ---------------------------------------------------------------------------

class TestContextClaims:
    def test_final_score_win_claim(self):
        match_stats = _match_stats("TeamA", "TeamB", home_score=3, away_score=1)
        findings, _, _ = _context_findings(match_stats, [], "TeamA", "TeamB")
        fs = next(f for f in findings if f["type"] == "final_score")
        assert fs["claim"] == "TeamA beat TeamB 3–1"

    def test_final_score_draw_claim(self):
        match_stats = _match_stats("TeamA", "TeamB", home_score=2, away_score=2)
        findings, _, _ = _context_findings(match_stats, [], "TeamA", "TeamB")
        fs = next(f for f in findings if f["type"] == "final_score")
        assert fs["claim"] == "TeamA and TeamB drew 2–2"

    def test_goal_claim(self):
        match_stats = _match_stats("TeamA", "TeamB", home_score=1, away_score=0)
        shots = [_shot("TeamA", "Striker", minute=10, period=1)]
        findings, _, _ = _context_findings(match_stats, shots, "TeamA", "TeamB")
        goal = next(f for f in findings if f["type"] == "goal")
        assert goal["claim"] == "Striker scored for TeamA (11')"

    def test_game_state_level_then_leading_claims(self):
        match_stats = _match_stats("TeamA", "TeamB", home_score=1, away_score=0)
        shots = [_shot("TeamA", "Striker", minute=10, period=1)]
        findings, _, _ = _context_findings(match_stats, shots, "TeamA", "TeamB")
        level, leading = [f for f in findings if f["type"] == "game_state"]
        assert level["claim"] == "the score was level at 0-0 from kick-off to 11'"
        assert leading["claim"] == "TeamA led 1-0 from 11' to full time"


# ---------------------------------------------------------------------------
# Structure: formation, formation_change, role_change, substitution
# ---------------------------------------------------------------------------

class TestStructureClaims:
    def test_formation_claim(self):
        # A second period after this one, so its to_minute renders as a real
        # minute rather than "full time" (which only the match's last period gets).
        formation = {"TeamA": _formation_team([
            _formation_period("4-4-2", 0, 1, 45, 2, [_formation_player(1, "Player One", "P One", "Left Back")]),
            _formation_period("4-3-3", 45, 2, 90, 2, [_formation_player(1, "Player One", "P One", "Left Back")]),
        ])}
        findings, _ = _structure_findings(formation, {"teams": {}}, {}, [], "TeamA")
        f = next(x for x in findings if x["type"] == "formation" and x["window"]["index"] == 0)
        assert f["claim"] == "TeamA played a 4-4-2 from kick-off to 46'"

    def test_formation_change_claim(self):
        periods = [
            _formation_period("4-4-2", 0, 1, 60, 2, [_formation_player(1, "P1", "P1", "Left Back")]),
            _formation_period("4-3-3", 60, 2, 90, 2, [_formation_player(1, "P1", "P1", "Left Back")]),
        ]
        formation = {"TeamA": _formation_team(periods)}
        findings, _ = _structure_findings(formation, {"teams": {}}, {}, [], "TeamA")
        fc = next(x for x in findings if x["type"] == "formation_change")
        assert fc["claim"] == "TeamA changed from a 4-4-2 to a 4-3-3 (61')"

    def test_role_change_claim(self):
        periods = [
            _formation_period("4-4-2", 0, 1, 60, 2, [_formation_player(1, "Full Name", "Display Name", "Left Back")]),
            _formation_period("4-4-2", 60, 2, 90, 2, [_formation_player(1, "Full Name", "Display Name", "Right Back")]),
        ]
        formation = {"TeamA": _formation_team(periods)}
        findings, _ = _structure_findings(formation, {"teams": {}}, {}, [], "TeamA")
        rc = next(x for x in findings if x["type"] == "role_change")
        assert rc["claim"] == "Display Name moved from Left Back to Right Back (61')"

    def test_substitution_claim_resolves_outgoing_display_name_via_lookup(self):
        # replaced_player is a bare full-name string in substitutes.json —
        # the display name has to come from the cross-file lookup.
        formation = {"TeamA": _formation_team([])}
        substitutes = {"teams": {"TeamA": [
            _substitute("Sub On Full", "Sub On", on_minute=70, on_period=2, replaced_player="Sub Off Full"),
        ]}}
        lookup = {"Sub Off Full": "Sub Off"}
        findings, _ = _structure_findings(formation, substitutes, lookup, [], "TeamA")
        sub = next(x for x in findings if x["type"] == "substitution")
        assert sub["claim"] == "Sub On replaced Sub Off for TeamA (71')"


# ---------------------------------------------------------------------------
# Shape in possession: player_zone (lane / mixed), team_height (own/opposition)
# ---------------------------------------------------------------------------

class TestInPossessionClaims:
    def test_player_zone_lane_claim(self):
        # Every touch in one lane — comfortably over MODAL_SHARE, not mixed.
        # A second period after this one keeps its to_minute from rendering
        # as "full time" (reserved for the match's actual last period).
        node = _on_ball_node(1, "Full Name", "Display", x=50, y=10, event_count=20, lane_counts={
            **_ZERO_LANE_COUNTS, "left_wing": 20,
        })
        team_shape = {"TeamA": _team_shape_team([
            _on_ball_period(0, 1, 45, 2, [node]),
            _on_ball_period(45, 2, 90, 2, [node]),
        ])}
        formation = {"TeamA": _formation_team([_formation_period("4-4-2", 0, 1, 90, 2, [
            _formation_player(1, "Full Name", "Display", "Left Wing"),
        ])])}
        findings, _ = _in_possession_findings(team_shape, formation, [], "TeamA")
        pz = next(f for f in findings if f["type"] == "player_zone" and f["window"]["index"] == 0)
        assert pz["label"] == "left_wing"
        assert pz["claim"] == "Display took 20 of 20 touches on the left wing (kick-off to 46')"

    def test_player_zone_mixed_lane_claim(self):
        # Top lane's share (9/20 = 45%) is below MODAL_SHARE (50%) -> mixed.
        node = _on_ball_node(1, "Full Name", "Display", x=50, y=10, event_count=20, lane_counts={
            **_ZERO_LANE_COUNTS, "left_wing": 9, "left_half_space": 8, "centre": 3,
        })
        team_shape = {"TeamA": _team_shape_team([
            _on_ball_period(0, 1, 45, 2, [node]),
            _on_ball_period(45, 2, 90, 2, [node]),
        ])}
        formation = {"TeamA": _formation_team([_formation_period("4-4-2", 0, 1, 90, 2, [
            _formation_player(1, "Full Name", "Display", "Left Wing"),
        ])])}
        findings, _ = _in_possession_findings(team_shape, formation, [], "TeamA")
        pz = next(f for f in findings if f["type"] == "player_zone" and f["window"]["index"] == 0)
        assert pz["label"] == "mixed"
        assert pz["claim"] == "Display split touches between the left wing (9) and the left half-space (8) (kick-off to 46')"

    def test_team_height_claims_both_labels(self):
        # 8 eligible outfield nodes exactly meets MIN_ELIGIBLE_OUTFIELD, so
        # team_height/team_width are NOT suppressed.
        opposition_half_players = [
            _on_ball_node(i, f"Player {i}", f"P{i}", x=70.0, y=float(i), event_count=15, lane_counts=dict(_ZERO_LANE_COUNTS))
            for i in range(1, 9)
        ]
        own_half_players = [
            _on_ball_node(i, f"Player {i}", f"P{i}", x=50.0, y=float(i), event_count=15, lane_counts=dict(_ZERO_LANE_COUNTS))
            for i in range(1, 9)
        ]
        formation_players = [_formation_player(i, f"Player {i}", f"P{i}", "Left Back") for i in range(1, 9)]
        formation = {
            "TeamA": _formation_team([_formation_period("4-4-2", 0, 1, 90, 2, formation_players)]),
            "TeamB": _formation_team([_formation_period("4-4-2", 0, 1, 90, 2, formation_players)]),
        }
        # A second period after the one under test, so its to_minute renders
        # as a real minute rather than "full time".
        team_shape = {
            "TeamA": _team_shape_team([
                _on_ball_period(0, 1, 45, 2, opposition_half_players),
                _on_ball_period(45, 2, 90, 2, opposition_half_players),
            ]),
            "TeamB": _team_shape_team([
                _on_ball_period(0, 1, 45, 2, own_half_players),
                _on_ball_period(45, 2, 90, 2, own_half_players),
            ]),
        }
        findings, suppressed = _in_possession_findings(team_shape, formation, [], "TeamA")
        assert suppressed == []
        th_a = next(f for f in findings if f["type"] == "team_height" and f["team"] == "TeamA" and f["window"]["index"] == 0)
        th_b = next(f for f in findings if f["type"] == "team_height" and f["team"] == "TeamB" and f["window"]["index"] == 0)
        assert th_a["label"] == "opposition_half"
        assert th_a["claim"] == "TeamA's average position in possession was in the opposition half (kick-off to 46')"
        assert th_b["label"] == "own_half"
        assert th_b["claim"] == "TeamB's average position in possession was in their own half (kick-off to 46')"


# ---------------------------------------------------------------------------
# Passing structure: hub/no_hub/top_pair, and their threshold edges
# ---------------------------------------------------------------------------

class TestPassingThresholdEdges:
    def test_share_of_exactly_hub_share_is_a_hub(self):
        # HUB_SHARE is ">=", so a share landing exactly on 0.15 must count.
        # window_passes=100; (made + received) / (2*100) == 0.15 -> made+received == 30.
        nodes = [_pn_node("A", "A Display", passes=5), _pn_node("B", "B Display", passes=95)]
        edges = [{"from": "B", "to": "A", "count": 25}]  # A: made=5, received=25 -> share=30/200=0.15
        pass_network = {"TeamA": {"windows": [_pn_window(0, 0, 1, 45, 2, nodes, edges)]}}
        findings, suppressed = _passing_findings(pass_network, [], "TeamA")
        assert suppressed == []
        hub_a = next(f for f in findings if f["type"] == "hub" and f["subject"]["player"] == "A")
        assert hub_a["value"] == 0.15

    def test_window_of_exactly_min_window_passes_is_not_suppressed(self):
        # MIN_WINDOW_PASSES suppression is "<", so exactly 40 must still compute.
        nodes = [_pn_node("A", "A Display", passes=20), _pn_node("B", "B Display", passes=20)]
        pass_network = {"TeamA": {"windows": [_pn_window(0, 0, 1, 45, 2, nodes, edges=[])]}}
        findings, suppressed = _passing_findings(pass_network, [], "TeamA")
        assert suppressed == []
        assert any(f["type"] == "concentration" for f in findings)

    def test_window_of_min_window_passes_minus_one_is_suppressed(self):
        nodes = [_pn_node("A", "A Display", passes=19), _pn_node("B", "B Display", passes=20)]
        pass_network = {"TeamA": {"windows": [_pn_window(0, 0, 1, 45, 2, nodes, edges=[])]}}
        findings, suppressed = _passing_findings(pass_network, [], "TeamA")
        assert findings == []
        assert {s["type"] for s in suppressed} == {"hub", "no_hub", "top_pair", "concentration"}
        assert all(s["reason"] == "MIN_WINDOW_PASSES" for s in suppressed)

    def test_tie_at_the_top_pair_cut_includes_every_tied_pair(self):
        # Ranked bidirectional totals: A-B=20, C-D=15, A-C=10, B-D=10 (tied
        # for 3rd), A-D absent. The cutoff is the 3rd-highest DISTINCT total
        # (10), so both pairs tied there must be emitted -- 4 pairs, not 3.
        nodes = [_pn_node(p, p, passes=30) for p in "ABCD"]
        edges = [
            {"from": "A", "to": "B", "count": 20},
            {"from": "C", "to": "D", "count": 15},
            {"from": "A", "to": "C", "count": 10},
            {"from": "B", "to": "D", "count": 10},
        ]
        pass_network = {"TeamA": {"windows": [_pn_window(0, 0, 1, 45, 2, nodes, edges)]}}
        findings, _ = _passing_findings(pass_network, [], "TeamA")
        top_pairs = [f for f in findings if f["type"] == "top_pair"]
        assert len(top_pairs) == 4
        assert sorted(f["value"] for f in top_pairs) == [10, 10, 15, 20]

    def test_hub_claim(self):
        nodes = [_pn_node("A", "A Display", passes=50), _pn_node("B", "B Display", passes=0)]
        edges = [{"from": "A", "to": "B", "count": 0}]
        # A second window after this one, so its to_minute renders as a real
        # minute rather than "full time".
        pass_network = {"TeamA": {"windows": [
            _pn_window(0, 0, 1, 45, 2, nodes, edges),
            _pn_window(1, 45, 2, 90, 2, nodes, edges),
        ]}}
        findings, _ = _passing_findings(pass_network, [], "TeamA")
        hub = next(f for f in findings if f["type"] == "hub" and f["subject"]["player"] == "A" and f["window"]["index"] == 0)
        # Involvement share divides by 2*window_passes (one "slot" for the
        # maker, one for the receiver), so making every pass but receiving
        # none caps out at 50%, not 100%.
        assert hub["claim"] == "A Display was a hub for TeamA, involved in 50.0% of passes (kick-off to 46')"

    def test_no_hub_claim(self):
        # 4 players, nobody reaches HUB_SHARE on their own.
        nodes = [_pn_node(p, p, passes=10) for p in "ABCD"]
        pass_network = {"TeamA": {"windows": [
            _pn_window(0, 0, 1, 45, 2, nodes, edges=[]),
            _pn_window(1, 45, 2, 90, 2, nodes, edges=[]),
        ]}}
        findings, _ = _passing_findings(pass_network, [], "TeamA")
        no_hub = next(f for f in findings if f["type"] == "no_hub" and f["window"]["index"] == 0)
        assert no_hub["claim"] == "TeamA's passing had no single hub; the most involved player, A, had 12.5% (kick-off to 46')"

    def test_top_pair_claim(self):
        nodes = [_pn_node("A", "A Display", passes=30), _pn_node("B", "B Display", passes=10)]
        edges = [{"from": "A", "to": "B", "count": 8}]
        pass_network = {"TeamA": {"windows": [
            _pn_window(0, 0, 1, 45, 2, nodes, edges),
            _pn_window(1, 45, 2, 90, 2, nodes, edges),
        ]}}
        findings, _ = _passing_findings(pass_network, [], "TeamA")
        pair = next(f for f in findings if f["type"] == "top_pair" and f["window"]["index"] == 0)
        # The player who made more passes is named first ("a").
        assert pair["claim"] == "A Display and B Display combined 8 times (kick-off to 46')"


# ---------------------------------------------------------------------------
# Cross-cutting: comparison (block_height/team_height/concentration), change
# ---------------------------------------------------------------------------

_WHOLE_MATCH_WINDOW = {"index": 0, "from_minute": 0, "to_minute": None, "source": "whole_match", "text": "kick-off to full time"}
_W0_WINDOW = {"index": 0, "from_minute": 0, "to_minute": 45, "source": "on_ball_period", "text": "kick-off to 46'"}


class TestCrossCuttingClaims:
    def test_comparison_block_height_claim(self):
        base = [
            _fake_finding("block_height", "TeamA", 50.0, window=_WHOLE_MATCH_WINDOW),
            _fake_finding("block_height", "TeamB", 40.0, window=_WHOLE_MATCH_WINDOW),
        ]
        out, _ = _cross_cutting_findings(base, "TeamA", "TeamB")
        comp = next(f for f in out if f["type"] == "comparison" and f["id"].startswith("cross.comparison.block_height"))
        assert comp["claim"] == "TeamB's average out-of-possession position was 10.0 yards deeper than TeamA's"

    def test_comparison_team_height_claim(self):
        base = [
            _fake_finding("team_height", "TeamA", 65.0, window=_W0_WINDOW),
            _fake_finding("team_height", "TeamB", 55.0, window=_W0_WINDOW),
        ]
        out, _ = _cross_cutting_findings(base, "TeamA", "TeamB")
        comp = next(f for f in out if f["type"] == "comparison" and f["id"].startswith("cross.comparison.team_height"))
        assert comp["claim"] == "TeamA's average position in possession was 10.0 yards higher than TeamB's (TeamA kick-off to 46', TeamB kick-off to 46')"

    def test_comparison_concentration_claim(self):
        base = [
            _fake_finding("concentration", "TeamA", 0.45, window=_W0_WINDOW),
            _fake_finding("concentration", "TeamB", 0.30, window=_W0_WINDOW),
        ]
        out, _ = _cross_cutting_findings(base, "TeamA", "TeamB")
        comp = next(f for f in out if f["type"] == "comparison" and f["id"].startswith("cross.comparison.concentration"))
        assert comp["claim"] == "TeamA's passing was more concentrated than TeamB's: the top three players had 45.0% of involvement against 30.0% (kick-off to 46')"

    def test_change_hub_claim(self):
        window_0 = {"index": 0, "from_minute": 0, "to_minute": 45, "source": "pass_network_window", "text": "kick-off to 46'"}
        window_1 = {"index": 1, "from_minute": 45, "to_minute": 90, "source": "pass_network_window", "text": "46' to full time"}
        subject = {"player": "Full Name", "display_name": "Display Name"}
        base = [
            _fake_finding("hub", "TeamA", 0.20, window=window_0, subject=subject),
            _fake_finding("hub", "TeamA", 0.10, window=window_1, subject=subject),
        ]
        out, _ = _cross_cutting_findings(base, "TeamA", "TeamB")
        change = next(f for f in out if f["type"] == "change")
        assert change["label"] == "fell"
        assert change["claim"] == "Display Name's passing involvement fell from 20.0% to 10.0% (kick-off to 46' to 46' to full time)"
