"""Integration test: extract_team_shape_off_ball()'s corrected centroid against
the real Euro 2024 Final match — DATA-SPEC-v2 Part 0's acceptance criterion.

Direct regression test for D1 (the off-ball centroid pooled two mirrored 360
frames before the Part 0 fix — DATA-SPEC-v2 §A). "Acceptance: regenerated
centroid x is 55.05 ± 0.1 for Spain and 45.98 ± 0.1 for England." Checking
this with a live extractor run, not by reading the committed JSON, catches a
regression as soon as the extractor changes, not only when someone happens to
re-run and re-commit the fixture. Part 3's broader integration test absorbs
this once it exists.
"""

import pytest

from statsbomb.extract_team_shape import extract_team_shape_off_ball

pytestmark = pytest.mark.integration


def test_spain_off_ball_centroid_x(match_id):
    off_ball = extract_team_shape_off_ball(match_id, "Spain")
    assert off_ball["centroid"]["x"] == pytest.approx(55.05, abs=0.1)


def test_england_off_ball_centroid_x(match_id):
    off_ball = extract_team_shape_off_ball(match_id, "England")
    assert off_ball["centroid"]["x"] == pytest.approx(45.98, abs=0.1)
