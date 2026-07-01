# CLAUDE.md — football-analytics

## Project
A football analytics codebase built as modular, reusable components spanning the
full stack: data **extraction → transformation → rendering**. Python owns
extraction and transformation; D3 (JavaScript, ES modules) owns rendering. Each
component is built end-to-end against real data, then reused across higher-level
views (dashboards).

## Architecture — the seam
- **Python** extracts from StatsBomb and transforms into clean, analysis-ready data.
- **D3 / JS** renders. It never touches the StatsBomb schema directly.
- **Contract between them:** flat JSON written to `sample_data/`. Components consume
  this JSON. Keep the contract minimal — do not emit fields the consumer doesn't use.
- **Coordinates:** StatsBomb-native 120×80 (yards). The pitch component handles pixel
  mapping (`px` / `pxPerYard`); pass native coordinates through to it untouched.

## Stack
- **Python:** `statsbombpy`, `pandas`, `numpy`, `mplsoccer` (static figures).
  Package manager: **`uv`**.
- **Viz:** **D3** as ES modules.
- **Data:** StatsBomb open data, including 360 freeze frames.
- **Layout:** flat JSON in `sample_data/`; Python package in `src/statsbomb`;
  D3 components in `src/footballd3/components/`.

## Conventions (rules)
- **Real IDs only.** Never hardcode or fabricate match/season IDs. Resolve live via
  `sb.competitions()` then `sb.matches()`. If an ID can't be resolved confidently,
  stop and ask.
- **Known gotcha:** `sb.frames()` raises `InvalidIndexError` on `statsbombpy` v1.18
  for Euro 2024 match IDs. Workaround: read 360 frames directly from the
  `statsbomb/open-data` GitHub raw JSON.
- **Build vertically.** Finish one component end-to-end (extract → transform → render)
  before starting the next. Data leads viz by one component; the render is what
  validates the transform's contract.
- **Extract, don't speculate.** Shared utilities and abstractions are pulled out once
  a pattern repeats across real components — not designed up front. Avoid premature
  abstraction.
- **Real data only.** Build and test components against real exported data, never
  fabricated inputs.
- **The code is the source of truth, not this file.** Update this file whenever an
  interface or contract changes. Do not record API signatures from memory — read them
  from the actual module.
- **Player names.** Resolve display names in Python, never in D3. The rule is a
  coalesce: `display_name = player_nickname or player_name`. `player_nickname` comes
  from `sb.lineups(match_id)` (it is NOT on events) and is frequently null — fall back
  to `player_name` when absent. Join nickname onto event/frame data by `player_id`,
  never by name string. Emit a resolved `display_name` into the JSON contract so
  components render a label and never see the nickname-vs-name logic. Do not build a
  manual name-override map up front; add single entries lazily only for names that are
  actually unreadable when rendered (consistent with "extract, don't speculate").
- **Component Description.** For each component, provide a brief description of it's purpose and how to interpret it.

## Documentation standard
Every change must leave the code documented. "Documented" means:
- **Python:** every module has a header docstring; every public function and class has
  a docstring (one consistent style per module). Inline comments explain *why* for
  non-obvious logic, not *what* for every line.
- **D3 / JS:** every exported function or component has a JSDoc block covering its
  parameters, return shape, and a one-line purpose.
- **Each component directory** carries a `README.md` covering what the component does,
  its JSON contract (input shape), and a minimal usage example.

This standard is **enforced, not requested.** `scripts/check_docs.sh` is wired into the
Claude Code Stop hook (which blocks finishing while docs are missing), git pre-commit,
and CI. A turn is not done until the gate passes. Existence of docs is gated
automatically; quality is on you and code review.

## JSON contracts (defined so far)
- **Shot:** `{ x, y, xg, outcome, is_goal, team, player, minute }` ->
  `sample_data/shots_{match_id}.json`. `xg` comes from `shot_statsbomb_xg`; shots are
  `type == "Shot"` events. `xg` drives marker size; `outcome` / `is_goal` drive color.
- **Freeze frame:** `{ ball: {x, y}, frame: [{ x, y, teammate, actor, keeper }],
  visible_area, metadata }`.
- **Convex hull:** `{ hulls: [{ sides: [{ side, team_name, hull_vertices, area, player_count }], metadata }], match_metadata }` ->
  `sample_data/convex_hull_{match_id}_goals.json`. `hulls[]` is parallel to `goals[]`
  in the freeze-frame file; pair by `metadata.event_id`. `side` is `"offense"|"defense"`
  resolved from `possession_team`; keeper excluded by default. Vertices in 120×80 yards.
- **Progressive map:** `{ team, actions: [{ action_type, display_name, x0, y0, x1, y1, completed, progressive, distance_gained, minute }], params: { progressive_threshold }, metadata }` ->
  `sample_data/progressive_map_{match_id}_{team_slug}.json`. Emits ALL open-play passes and
  carries; `progressive: bool` flags the 25%-of-remaining-distance-to-goal rule (goal centre
  (120, 40), threshold 0.25). Set pieces excluded via `play_pattern`. Passes: completed AND
  incomplete (pass_outcome NaN = completed). Carries: `completed` always true — StatsBomb has
  no incomplete-carry event. `distance_gained` is positive (toward goal) or negative (away).
- **Player label:** any contract carrying players includes `display_name` (resolved
  Python-side via the nickname/name coalesce above). Components render `display_name`
  verbatim; they do not receive `player_name`/`player_nickname` separately.

## Components
Existing:
- **`pitch.js`** — D3 ES module rendering the 120×80 StatsBomb pitch. Config: `mode`
  (full / half), `orientation` (horizontal / vertical), `theme`, goals visibility,
  `pxPerYard`. (Exact API and return shape: read from the module — do not assume.)
- **`convexHull.js`** — overlay: convex hull territory polygons for one or both teams
  at a single freeze-frame instant. Inserts behind the freeze-frame dot layer. Config:
  `toggle` (offense/defense/both), colors, opacity, `mirrorX`. Must match the `mirrorX`
  value passed to `createFreezeFrame()`. Keeper excluded from hull geometry by default.
- **`progressiveMap.js`** — overlay: arrow-on-pitch rendering of progressive passes and
  carries. Composes on pitch.js (receives pitch object, never creates the pitch). Progressive
  = StatsBomb's 25%-of-remaining-distance-to-goal-centre rule; set pieces excluded via
  `play_pattern`. Passes show attempts + completions (solid vs dashed); carries are
  completed-only. Config: `toggle` (passes/carries/both), `player` filter (display_name or
  null), `distanceWeight` (off by default). Returns `{ g, update({ toggle?, player? }) }`.

Planned — build one at a time, vertically; this is a roadmap, not a build-all-now list:
- **Tier 1:** pitch map (event scatter), shot map, pass map / network, freeze-frame
  snapshot, heatmap / density, match stat breakdown, player formation. ✓ all built
- **Tier 2:** convex hull / territory ✓, progressive pass / carry map ✓, timeline / event
  strip, Voronoi, momentum chart, goal animations, AI-summarized data.
- **Tier 3:** radar, rolling-average line, distribution (violin / beeswarm), joyplot.

Views (dashboards composed from components): team match analysis, player match
analysis, team season/tournament, player season/tournament, player fitness,
component library.

## Visual conventions
- Background `#FAF7F0`; text `#171717` (secondary `#525252`); structure `#E5E5E5`;
  focal accent `#9F1239`; secondary accent `#1E3A5F`.
- Type: Fraunces (headlines), Geist (body), Geist Mono (labels / code).
- Pitch themes: `whiteboard`, `green`. Goals on shot maps use the focal accent
  (`#9F1239`).