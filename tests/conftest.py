"""Shared pytest fixtures for the statsbomb test suite.

Adds libs/ to sys.path (mirrors scripts/extract_euro2024.py's own approach) so
tests can `import statsbomb` without the package being pip-installed.

raw_events/raw_lineups are session-scoped: statsbombpy already wraps sb.* calls in
a requests_cache session (see statsbombpy.api_client, expire_after=600s), but that
cache lives in a fresh mkdtemp() per process — it speeds up repeated identical
calls WITHIN one pytest run, not across separate `uv run` invocations. Session
scope means the one-time live-network cost (~10-20s cold) is paid once per test
run, not once per test that needs match data.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "libs"))

import pytest
from statsbombpy import sb

MATCH_ID = 3943043  # Euro 2024 Final, Spain vs England — the match every sample file targets.


@pytest.fixture(scope="session")
def match_id() -> int:
    """The StatsBomb match ID used by every integration test in this suite.

    Returns:
        int: 3943043 (UEFA Euro 2024 Final, Spain vs England).
    """
    return MATCH_ID


@pytest.fixture(scope="session")
def raw_events(match_id):
    """Full raw event DataFrame for the test match, fetched once per test run.

    Args:
        match_id (int): StatsBomb match ID, from the match_id fixture.

    Returns:
        pd.DataFrame: sb.events(match_id=match_id)'s return value.
    """
    return sb.events(match_id=match_id)


@pytest.fixture(scope="session")
def raw_lineups(match_id):
    """Full raw lineups dict (team -> DataFrame) for the test match.

    Args:
        match_id (int): StatsBomb match ID, from the match_id fixture.

    Returns:
        dict[str, pd.DataFrame]: sb.lineups(match_id=match_id)'s return value.
    """
    return sb.lineups(match_id=match_id)
