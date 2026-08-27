"""statsbomb — extraction and transformation layer for StatsBomb open data.

Each extract_* module provides a public function that accepts a match_id and
returns a tidy pandas DataFrame. JSON output for the footballd3 components is
produced by calling main() in each module.

Usage example:
    from statsbomb import extract_shots
    df = extract_shots(3869685)   # Euro 2024 Final match ID

Shared helpers (resolve_match, fetch_match_info, build_nickname_lookup, etc.)
are available directly from statsbomb.utils.
"""

from .extract_shots import extract_shots
from .extract_freeze_frame import extract_freeze_frame
from .extract_convex_hull import extract_convex_hull
from .extract_progressive_map import extract_progressive_map
from .extract_possession import extract_possession
from .extract_heatmap import extract_heatmap
from .extract_pass_network import extract_pass_network
from .extract_formation import extract_formation
from .extract_team_shape import extract_team_shape_on_ball, extract_team_shape_off_ball
from .extract_xt import extract_xt
from .extract_momentum import extract_momentum
from .extract_goal_animation import extract_goal_animation, extract_play_animation
from .extract_match_stats import extract_match_stats
from .generate_match_summary import generate_match_summary

__all__ = [
    "extract_shots",
    "extract_freeze_frame",
    "extract_convex_hull",
    "extract_progressive_map",
    "extract_possession",
    "extract_heatmap",
    "extract_pass_network",
    "extract_formation",
    "extract_team_shape_on_ball",
    "extract_team_shape_off_ball",
    "extract_xt",
    "extract_momentum",
    "extract_goal_animation",
    "extract_play_animation",
    "extract_match_stats",
    "generate_match_summary",
]
