"""Shared constants, display formats and claim templates for the
match-summary tactical findings layer.

Single source of truth for every threshold, display format and claim
template in `ai/match_summary/DATA-SPEC-v2.md` — seam rule 4: "Every
threshold, display format and claim template is a named constant in one
file." Part 0 (`extract_team_shape.py`) only needs the coordinate edges;
Part 2 (`derive_tactical_findings.py`) is the consumer of everything else
here — it builds every finding's label and claim from these constants, and
nothing else in the codebase defines a threshold, display format or claim
template.

Public API:
    DEFINITIONS_VERSION (str)
    PITCH_WIDTH, PITCH_HEIGHT (int)
    LANE_EDGES, BAND_EDGES (list[tuple[str, float, float]])
    lane_for_y(y) -> str
    band_for_x(x) -> str
    LANE_DISPLAY, BAND_DISPLAY (dict[str, str])
    DISPLAY_FORMATS (dict[str, Callable[[float], str]])
    display_minute(minute, period) -> str
    CLAIM_TEMPLATES (dict[str, str | dict[str, str]])
    CONNECTIVES (dict[str, frozenset[str]])
    CAUSAL_TERMS, BANNED_TERMS (frozenset[str])
    Thresholds: HUB_SHARE, MIN_WINDOW_PASSES, MIN_NODE_EVENTS,
        MIN_ELIGIBLE_OUTFIELD, MODAL_SHARE, MIN_PAIR_COUNT,
        COMPARE_MIN_YARDS, COMPARE_MIN_POINTS, CHANGE_MIN_SHARE
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


# Lane/band label -> prose, exactly as DATA-SPEC-v2's own examples write them
# (note "half-space" is hyphenated, so this isn't a mechanical
# underscore-to-space substitution for every label).
LANE_DISPLAY: dict[str, str] = {
    "left_wing": "left wing",
    "left_half_space": "left half-space",
    "centre": "centre",
    "right_half_space": "right half-space",
    "right_wing": "right wing",
}

BAND_DISPLAY: dict[str, str] = {
    "own_third": "own third",
    "own_half": "own half",
    "opposition_half": "opposition half",
    "final_third": "final third",
}

# "percentages to one decimal with a % sign, yards to one decimal followed
# by 'yards', counts as integers" (DATA-SPEC-v2, "Number formats").
DISPLAY_FORMATS: dict[str, "Callable[[float], str]"] = {
    "percentage": lambda v: f"{v:.1f}%",
    "yards": lambda v: f"{v:.1f} yards",
    "count": lambda v: str(int(v)),
}


def display_minute(minute: int, period: int) -> str:
    """Render a StatsBomb minute as the prose minute string.

    StatsBomb `minute` is elapsed minutes and keeps counting through
    stoppage time; the second-half clock restarts near 45' rather than
    continuing from where the first half ended (see
    `_on_ball_periods`/`_pressure_regain`'s half-time-boundary handling
    elsewhere in this package). This renders the stoppage-time-aware prose
    form: "45'" is the last regular first-half minute, "45+1'" is the first
    minute of first-half stoppage, and so on for the second half at 90'.

    Args:
        minute (int): StatsBomb elapsed minute.
        period (int): Match period (1 or 2 — see Raises).

    Returns:
        str: e.g. "1'", "45'", "45+1'", "46'", "90+1'".

    Raises:
        ValueError: If period is not 1 or 2. Extra time is out of scope for
            this spec.
    """
    if period > 2:
        raise ValueError(f"display_minute: period {period} is out of scope (extra time)")
    if period == 1:
        if minute >= 45:
            return f"45+{minute - 44}'"
        return f"{minute + 1}'"
    if period == 2:
        if minute >= 90:
            return f"90+{minute - 89}'"
        return f"{minute + 1}'"
    raise ValueError(f"display_minute: unexpected period {period}")


# --- Thresholds (DATA-SPEC-v2 "Definitions and thresholds" / "Decisions") --
# All provisional, calibrated on one match (decision 11).

# Shape in possession.
MODAL_SHARE = 0.50           # player_zone: modal lane/band share needed to avoid "mixed".
MIN_NODE_EVENTS = 10          # player_zone: suppressed below this many touches.
MIN_ELIGIBLE_OUTFIELD = 8     # team_height/team_width: suppressed below this many eligible nodes.

# Passing structure.
HUB_SHARE = 0.15              # hub: involvement share needed to be a hub.
MIN_WINDOW_PASSES = 40        # passing findings suppressed below this many completed passes in the window.
MIN_PAIR_COUNT = 8            # top_pair: minimum bidirectional total to be emitted.
CHANGE_MIN_SHARE = 0.04       # change (hub): minimum involvement-share move, and must cross HUB_SHARE.

# Cross-cutting (comparison).
COMPARE_MIN_YARDS = 5         # comparison (block_height, team_height, team_width): minimum gap to emit.
COMPARE_MIN_POINTS = 5        # comparison (concentration): minimum gap, in points, to emit.


# --- Claim templates (DATA-SPEC-v2 "Claims") -------------------------------
# One entry per row in the Claims table. Placeholders are filled by
# derive_tactical_findings.py (Part 2); values go through DISPLAY_FORMATS
# and lane/band values through LANE_DISPLAY/BAND_DISPLAY first. A few table
# rows wrote an alternation as "{a | b}" (unrenderable literally, since "|"
# can't both be markdown-table syntax and template syntax) — those become
# either a sub-dict keyed by the deciding label (final_score, game_state,
# player_zone, team_height) or a {direction} placeholder filled with the
# literal word (change hub: "rose"/"fell").
CLAIM_TEMPLATES: dict = {
    "final_score": {
        "win":  "{winner} beat {loser} {w}–{l}",
        "draw": "{home} and {away} drew {h}–{a}",
    },
    "goal": "{player} scored for {team} ({display_minute})",
    "game_state": {
        "leading": "{team} led {score} from {from} to {to}",
        "level":   "the score was level at {score} from {from} to {to}",
    },
    "formation": "{team} played a {formation} from {from} to {to}",
    "formation_change": "{team} changed from a {old} to a {new} ({display_minute})",
    "substitution": "{on} replaced {off} for {team} ({display_minute})",
    "role_change": "{player} moved from {old_position} to {new_position} ({display_minute})",
    "player_zone": {
        "lane":  "{player} took {n} of {total} touches on the {lane} ({window})",
        "mixed": "{player} split touches between the {lane1} ({n1}) and the {lane2} ({n2}) ({window})",
    },
    "team_height": {
        "own_half":        "{team}'s average position in possession was in their own half ({window})",
        "opposition_half": "{team}'s average position in possession was in the opposition half ({window})",
    },
    "hub": "{player} was a hub for {team}, involved in {share} of passes ({window})",
    "no_hub": "{team}'s passing had no single hub; the most involved player, {player}, had {share} ({window})",
    "top_pair": "{a} and {b} combined {n} times ({window})",
    "comparison": {
        "block_height":  "{deeper}'s average out-of-possession position was {gap} deeper than {other}'s",
        "team_height":   "{higher}'s average position in possession was {gap} higher than {other}'s ({higher} {window_a}, {other} {window_b})",
        "concentration": "{team}'s passing was more concentrated than {other}'s: the top three players had {a} of involvement against {b} ({window})",
    },
    "change": {
        "hub": "{player}'s passing involvement {direction} from {a} to {b} ({window_1} to {window_2})",
    },
}


# --- Linking rule (DATA-SPEC-v2 "Linking rule" / "Vocabulary") -------------
CONNECTIVES: dict[str, frozenset] = {
    "joining":  frozenset({"and", "while", "but", "also", "in contrast"}),
    # Allowed only when the sentence cites a minute-bearing finding
    # (goal, substitution, formation_change, role_change, game_state, change).
    "sequence": frozenset({"then", "after", "before", "following", "meanwhile"}),
}

CAUSAL_TERMS: frozenset = frozenset({
    "because", "forced", "allowed", "led to", "as a result",
    "which meant", "so", "therefore", "due to", "thanks to",
})

# "Banned everywhere": intent/fatigue/morale/motive words, plus every causal
# word above (a causal word is banned everywhere, not just between claims).
BANNED_TERMS: frozenset = frozenset({
    "intent", "fatigue", "morale", "wanted to", "looked to", "tried to",
}) | CAUSAL_TERMS
