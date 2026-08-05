"""Integration test: get_eligible_players() against the real Euro 2024 Final match.

Direct regression test for the bug found while building this: 4 of the match's 7
substitutions never triggered a Tactical Shift event, so a roster sourced from
formation periods (instead of sb.lineups()) would silently drop them. If a future
StatsBomb data revision or a code change reintroduces that dependency, this test
fails immediately instead of requiring another manual roster count.
"""

import pytest

from statsbomb.extract_substitutes import get_eligible_players

pytestmark = pytest.mark.integration


def test_exact_substitute_roster(match_id):
    roster = get_eligible_players(match_id)
    subs = roster[~roster["is_starter"]]

    england_subs = set(subs[subs["team"] == "England"]["display_name"])
    spain_subs = set(subs[subs["team"] == "Spain"]["display_name"])

    assert england_subs == {"Cole Palmer", "Ollie Watkins", "Ivan Toney"}
    assert spain_subs == {"Martín Zubimendi", "Mikel Oyarzabal", "Nacho", "Mikel Merino"}


def test_no_goalkeeper_in_eligible_roster(match_id):
    roster = get_eligible_players(match_id)
    assert "Goalkeeper" not in roster["position"].values
    assert "Jordan Pickford" not in roster["display_name"].values
    assert "Unai Simón" not in roster["display_name"].values


def test_player_id_is_unique_and_stable(match_id):
    roster = get_eligible_players(match_id)
    assert roster["player_id"].is_unique
    assert (roster["player_id"] > 0).all()


def test_eligible_count_matches_starters_plus_subs(match_id):
    roster = get_eligible_players(match_id)
    # 11 starters per team minus 1 GK each = 10 outfield starters per team (20
    # total), plus 3 England subs + 4 Spain subs = 27.
    assert len(roster) == 27
