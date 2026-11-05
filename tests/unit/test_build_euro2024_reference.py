"""Unit tests for scripts/build_euro2024_reference.py's pure helpers.
No network calls.
"""

import pandas as pd

from scripts.build_euro2024_reference import _undo_away_team_flip


class TestUndoAwayTeamFlip:
    def test_home_team_rows_are_untouched(self):
        actions = pd.DataFrame([
            {"team_id": 1, "start_x": 90.0, "start_y": 10.0, "end_x": 95.0, "end_y": 12.0},
        ])
        fixed = _undo_away_team_flip(actions, home_team_id=1)
        assert fixed.loc[0, "start_x"] == 90.0
        assert fixed.loc[0, "start_y"] == 10.0
        assert fixed.loc[0, "end_x"] == 95.0
        assert fixed.loc[0, "end_y"] == 12.0

    def test_away_team_rows_are_flipped_back(self):
        # convert_to_actions flipped this away-team action to
        # start_x=105-90=15, start_y=68-10=58 (field_length=105, field_width=68);
        # undoing it should restore the original 90/10.
        actions = pd.DataFrame([
            {"team_id": 2, "start_x": 15.0, "start_y": 58.0, "end_x": 10.0, "end_y": 56.0},
        ])
        fixed = _undo_away_team_flip(actions, home_team_id=1)
        assert fixed.loc[0, "start_x"] == 90.0
        assert fixed.loc[0, "start_y"] == 10.0
        assert fixed.loc[0, "end_x"] == 95.0
        assert fixed.loc[0, "end_y"] == 12.0

    def test_mixed_home_and_away_rows(self):
        actions = pd.DataFrame([
            {"team_id": 1, "start_x": 90.0, "start_y": 10.0, "end_x": 95.0, "end_y": 12.0},
            {"team_id": 2, "start_x": 15.0, "start_y": 58.0, "end_x": 10.0, "end_y": 56.0},
        ])
        fixed = _undo_away_team_flip(actions, home_team_id=1)
        assert list(fixed["start_x"]) == [90.0, 90.0]
        assert list(fixed["start_y"]) == [10.0, 10.0]

    def test_applying_twice_is_not_idempotent(self):
        # Sanity check on the fix's own logic: it's a flip, not a clamp —
        # applying it twice to the same (already-fixed) rows re-flips them,
        # it does not leave them unchanged. Guards against accidentally
        # calling this helper more than once on the same DataFrame.
        actions = pd.DataFrame([
            {"team_id": 2, "start_x": 15.0, "start_y": 58.0, "end_x": 10.0, "end_y": 56.0},
        ])
        once = _undo_away_team_flip(actions, home_team_id=1)
        twice = _undo_away_team_flip(once, home_team_id=1)
        assert list(twice["start_x"]) == list(actions["start_x"])
