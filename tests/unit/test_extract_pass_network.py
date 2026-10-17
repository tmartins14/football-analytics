"""Unit tests for extract_pass_network's window-building. No network calls.

Covers a regression found while backfilling Euro 2024 matches: two
substitutions landing on the same minute create a zero-length middle window,
which gets skipped — but `index` must stay contiguous among the windows that
*are* emitted, since `derive_tactical_findings.py`'s is_first/is_last checks
compare `index` against `len(windows) - 1`.
"""

import pandas as pd

from statsbomb.extract_pass_network import _build_windows


def _events(rows):
    return pd.DataFrame(rows)


class TestBuildWindowsSimultaneousSubstitutions:
    def test_two_subs_in_the_same_minute_do_not_create_an_index_gap(self):
        # Two substitutions both at minute 84 produce an empty [84, 84)
        # window, which _build_windows skips — before the fix, the next
        # (last) window kept the raw loop position (2) instead of its
        # emitted position (1), so index jumped 0 -> 2.
        events = _events([
            {"type": "Pass", "team": "TeamA", "minute": 10, "period": 2,
             "pass_outcome": None, "location": [50.0, 50.0], "player": "P1",
             "player_id": 1, "pass_recipient": "P2"},
            {"type": "Pass", "team": "TeamA", "minute": 90, "period": 2,
             "pass_outcome": None, "location": [60.0, 40.0], "player": "P3",
             "player_id": 3, "pass_recipient": None},
            {"type": "Substitution", "team": "TeamA", "minute": 84, "period": 2,
             "player": "A1", "substitution_replacement": "B1"},
            {"type": "Substitution", "team": "TeamA", "minute": 84, "period": 2,
             "player": "A2", "substitution_replacement": "B2"},
        ])

        windows, substitutions = _build_windows(events, "TeamA", nicknames={})

        assert len(substitutions) == 2
        # The zero-length [84, 84) window is skipped: only two windows emitted.
        assert len(windows) == 2
        assert [w["index"] for w in windows] == [0, 1]
        assert windows[0]["from_minute"] == 0
        assert windows[0]["to_minute"] == 84
        assert windows[-1]["from_minute"] == 84
        # Last window is still open-ended.
        assert windows[-1]["to_minute"] is None
        assert windows[-1]["to_period"] is None

    def test_no_simultaneous_subs_indices_still_contiguous(self):
        events = _events([
            {"type": "Pass", "team": "TeamA", "minute": 10, "period": 1,
             "pass_outcome": None, "location": [50.0, 50.0], "player": "P1",
             "player_id": 1, "pass_recipient": "P2"},
            {"type": "Pass", "team": "TeamA", "minute": 70, "period": 2,
             "pass_outcome": None, "location": [60.0, 40.0], "player": "P3",
             "player_id": 3, "pass_recipient": None},
            {"type": "Substitution", "team": "TeamA", "minute": 60, "period": 2,
             "player": "A1", "substitution_replacement": "B1"},
        ])

        windows, _ = _build_windows(events, "TeamA", nicknames={})

        assert [w["index"] for w in windows] == list(range(len(windows)))
