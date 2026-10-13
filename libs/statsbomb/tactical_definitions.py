"""Shared coordinate constants for the match-summary tactical findings layer.

Single source of truth for the pitch-coordinate conventions in
`ai/match_summary/DATA-SPEC-v2.md` ("Coordinate and display conventions").
Extractors import from here rather than defining their own copies of a lane
or band edge — seam rule 4 in that spec: "Every threshold, display format
and claim template is a named constant in one file."

This module starts deliberately small: Part 0 (`extract_team_shape.py`) only
needs the coordinate edges to compute `lane_counts`/`band_counts`. Part 1
extends this same file with `LANE_DISPLAY`, `BAND_DISPLAY`,
`DISPLAY_FORMATS`, `display_minute()`, `CLAIM_TEMPLATES`, `CONNECTIVES`,
`CAUSAL_TERMS`, `BANNED_TERMS` and the remaining thresholds — it does not
create a new file.

Public API:
    DEFINITIONS_VERSION (str)
    PITCH_WIDTH, PITCH_HEIGHT (int)
    LANE_EDGES, BAND_EDGES (list[tuple[str, float, float]])
    lane_for_y(y) -> str
    band_for_x(x) -> str
"""

DEFINITIONS_VERSION = "0.1.0"

PITCH_WIDTH = 120
PITCH_HEIGHT = 80

# (label, low, high), ordered low to high. Half-open [low, high) buckets,
# except the last bucket on the axis, which is closed — see lane_for_y/
# band_for_x. Edges are the penalty-area and six-yard-box lines.
LANE_EDGES: list[tuple[str, float, float]] = [
    ("left_wing", 0, 18),
    ("left_half_space", 18, 30),
    ("centre", 30, 50),
    ("right_half_space", 50, 62),
    ("right_wing", 62, 80),
]

BAND_EDGES: list[tuple[str, float, float]] = [
    ("own_third", 0, 40),
    ("own_half", 40, 60),
    ("opposition_half", 60, 80),
    ("final_third", 80, 120),
]


def lane_for_y(y: float) -> str:
    """Map a pitch y coordinate to its lane label.

    Buckets are half-open [low, high), except `right_wing`, which is closed
    ([62, 80]) so the far touchline itself has a bucket.

    Args:
        y (float): StatsBomb y coordinate, 0 (left touchline) to 80.

    Returns:
        str: One of the labels in `LANE_EDGES`.

    Raises:
        ValueError: If y is outside [0, 80].
    """
    if not (0 <= y <= PITCH_HEIGHT):
        raise ValueError(f"y={y} is outside the pitch (0-{PITCH_HEIGHT})")
    for label, low, high in LANE_EDGES:
        if low <= y < high or (high == PITCH_HEIGHT and y == high):
            return label
    raise AssertionError(f"y={y} matched no lane despite passing the bounds check")  # pragma: no cover


def band_for_x(x: float) -> str:
    """Map a pitch x coordinate to its band label.

    Buckets are half-open [low, high), except `final_third`, which is closed
    ([80, 120]) so the far goal line itself has a bucket.

    Args:
        x (float): StatsBomb x coordinate, 0 (own goal line) to 120.

    Returns:
        str: One of the labels in `BAND_EDGES`.

    Raises:
        ValueError: If x is outside [0, 120].
    """
    if not (0 <= x <= PITCH_WIDTH):
        raise ValueError(f"x={x} is outside the pitch (0-{PITCH_WIDTH})")
    for label, low, high in BAND_EDGES:
        if low <= x < high or (high == PITCH_WIDTH and x == high):
            return label
    raise AssertionError(f"x={x} matched no band despite passing the bounds check")  # pragma: no cover
