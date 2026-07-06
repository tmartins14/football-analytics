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
- **Contract between them:** flat JSON written to `src/footballd3/sample_data/`. Components consume
  this JSON. Keep the contract minimal — do not emit fields the consumer doesn't use.
- **Coordinates:** StatsBomb-native 120×80 (yards). The pitch component handles pixel
  mapping (`px` / `pxPerYard`); pass native coordinates through to it untouched.

## Stack
- **Python:** `statsbombpy`, `pandas`, `numpy`, `mplsoccer` (static figures).
  Package manager: **`uv`**.
- **Viz:** **D3** as ES modules.
- **Data:** StatsBomb open data, including 360 freeze frames.
- **Layout:** flat JSON in `src/footballd3/sample_data/`; Python package in `src/statsbomb`;
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
All files live under `src/footballd3/sample_data/`.

- **Shot:** `{ x, y, xg, outcome, is_goal, team, player, minute }` ->
  `shots_{match_id}.json`. `xg` comes from `shot_statsbomb_xg`; shots are
  `type == "Shot"` events. `xg` drives marker size; `outcome` / `is_goal` drive color.
- **Freeze frame:** `{ ball: {x, y}, frame: [{ x, y, teammate, actor, keeper }],
  visible_area, metadata }`.
- **Convex hull:** `{ hulls: [{ sides: [{ side, team_name, hull_vertices, area, player_count }], metadata }], match_metadata }` ->
  `convex_hull_{match_id}_goals.json`. `hulls[]` is parallel to `goals[]`
  in the freeze-frame file; pair by `metadata.event_id`. `side` is `"offense"|"defense"`
  resolved from `possession_team`; keeper excluded by default. Vertices in 120×80 yards.
- **Progressive map:** `{ team, actions: [{ action_type, display_name, x0, y0, x1, y1, completed, progressive, distance_gained, minute }], params: { progressive_threshold }, metadata }` ->
  `progressive_map_{match_id}_{team_slug}.json`. Emits ALL open-play passes and
  carries; `progressive: bool` flags the 25%-of-remaining-distance-to-goal rule (goal centre
  (120, 40), threshold 0.25). Set pieces excluded via `play_pattern`. Passes: completed AND
  incomplete (pass_outcome NaN = completed). Carries: `completed` always true — StatsBomb has
  no incomplete-carry event. `distance_gained` is positive (toward goal) or negative (away).
- **Possession:** `{ match_id, possession, team, events: [{ event_id, event_type, seconds, x, y, end_x, end_y, player, outcome }], metadata }` ->
  `possession_{match_id}_{possession}.json`. `seconds` is elapsed time within the possession
  (event timestamp minus first event's timestamp). `end_x`/`end_y` present for Pass, Carry,
  Shot; null for point events. `player` is the resolved `display_name`. `outcome` is the
  pass outcome string for Pass events (null = complete), null for all other types.
  Consumed by both `eventScatter.js` (spatial: x,y) and `timelineStrip.js` (temporal: seconds).
- **Player label:** any contract carrying players includes `display_name` (resolved
  Python-side via the nickname/name coalesce above). Components render `display_name`
  verbatim; they do not receive `player_name`/`player_nickname` separately.
- **Play animation / goal animation:** `{ goals: [{ window: {anchor_event_id, start_event_id, end_event_id, period, window_seconds, t_span_seconds}, frames: [{event_id, t_seconds, team, event_type, ball_x, ball_y, ball_end_x, ball_end_y, actor, outcome}], context: {goal?: {event_id, minute, second, scorer, team}}, metadata }], match_metadata }` ->
  `goal_animation_{match_id}.json`. One file per match; `goals[]` covers all goals in
  chronological order. General engine is `extract_play_animation(match_id, anchor_event_id,
  window_seconds)` → one clip dict; `extract_goal_animation` is a thin wrapper that finds all
  goals, calls the engine for each, and injects `context.goal`. `t_seconds` is **clip-relative**
  (0.0 at first frame); `window.t_span_seconds` = last frame's t_seconds (clip duration base).
  `team` field on each frame — both teams included. `ball_end_x/y` null for point events
  (Pressure, Duel, etc.) — ball stays put. `actor_x/y` omitted (always equal to `ball_x/y`).
  window_seconds=10 is a configurable choice, not canonical. Events included: Pass, Carry,
  Shot (ball moves) + Pressure, Duel, Interception, Ball Recovery (point events). Ball
  Receipt* excluded. Clip is period-isolated (never straddles halftime/extra-time boundary).

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

- **`eventScatter.js`** — general-purpose event scatter on the pitch. Renders any event array
  as markers at (x, y); events with end_x/end_y (Pass, Carry, Shot) also draw an arrow.
  Encodes event_type by color category (ball-movement=red, defensive=navy, terminal=gray).
  Ball Receipt* excluded by default (`includeBallReceipt: true` to opt in). Composes on
  pitch.js. Returns `{ g, update({ events?, filter? }) }`.
- **`timelineStrip.js`** — single-possession elapsed-seconds horizontal strip. Events are
  positioned on a real-time X axis (seconds within possession); glyphs are colored circles
  with a single letter indicating event type. Overlapping events at near-identical timestamps
  are stacked vertically (deterministic, bin-based). Does NOT compose on pitch.js — standalone
  chart. Returns `{ svg, g, xScale, update({ events? }) }`.
- **`playAnimation.js`** — general time-windowed ball-path animation. Animates the ball's
  path through any event sequence bounded by an anchor event and a window_seconds duration.
  Both teams' events are included; each frame carries a `team` field. The first component
  with owned playback state (scrubber + play/pause via `d3.timer`). Composes on pitch.js.
  Ball moves along straight segments (event start → end); actors highlight at their event
  origins only (no between-event motion). Point events (Pressure, Duel) pause the ball.
  Returns `{ g, controls: { play(), pause(), seek(clipSeconds) }, update({ frames?, playbackSpeed? }) }`.
  Scrubber wired externally via `onTimeUpdate` callback. Default playbackSpeed=2.0×.
  DISCLAIMER in README: not tracking data; straight-line ball paths; window configurable.
  Produced by `extract_play_animation` (general) or `extract_goal_animation` (thin wrapper).

Planned — build one at a time, vertically; this is a roadmap, not a build-all-now list:
- **Tier 1:** pitch map (event scatter) ✓, shot map, pass map / network, freeze-frame
  snapshot, heatmap / density, match stat breakdown, player formation. ✓ all built
- **Tier 2:** convex hull / territory ✓, progressive pass / carry map ✓, timeline / event
  strip ✓, Voronoi, momentum chart ✓, goal animations ✓, AI-summarized data.
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