# footballd3 — component gallery

Local development harness for the footballd3 component library. Open the gallery
in a browser, edit a component file, refresh.

## Running

From the repo root:

```bash
python3 -m http.server 8000
```

Then open: `http://localhost:8000/libs/footballd3/index.html`

The server is required because ES modules don't load over `file://`.

## Structure

```
libs/footballd3/
  index.html                         ← gallery harness
  components/
    pitch/
      pitch.js                       ← StatsBomb 120×80 pitch base layer
      README.md
    shotMap/
      shotMap.js                     ← shot scatter on half-pitch; circle area = xG
      README.md
    passNetwork/
      passNetwork.js                 ← substitution-windowed directed pass network
      README.md
    freezeFrame/
      freezeFrame.js                 ← 360 freeze-frame dot overlay at goal instant
      README.md
    convexHull/
      convexHull.js                  ← territory polygons (offense/defense) at freeze-frame instant
      README.md
    heatmap/
      heatmap.js                     ← player on-ball KDE density surface
      README.md
    matchStats/
      matchStats.js                  ← match-level stat table (shots, possession, xG, ...)
      README.md
    comparisonBars/
      comparisonBars.js              ← generic home/away bar chart; consumed by matchStats
      README.md
    formation/
      formation.js                   ← declared formation + tactical-shift sequence
      README.md
    teamShape/
      teamShape.js                   ← empirical on-ball nodes + off-ball density cloud
      README.md
    progressiveMap/
      progressiveMap.js              ← progressive pass/carry arrows on full pitch
      README.md
    eventScatter/
      eventScatter.js                ← general event scatter on pitch; arrows for pass/carry/shot
      README.md
    timelineStrip/
      timelineStrip.js               ← possession elapsed-seconds strip (standalone, no pitch)
      README.md
    xtSurface/
      xtSurface.js                   ← xT grid heatmap surface beneath pitch markings
      README.md
    playAnimation/
      playAnimation.js               ← time-windowed ball-path animation with scrubber
      README.md
    momentumChart/
      momentumChart.js               ← per-minute xT momentum curve (horizontal or vertical)
      README.md
    cumulativeXgChart/
      cumulativeXgChart.js           ← per-team cumulative xG step chart (race chart) with G-chip overlay
      README.md
    momentumBarChart/
      momentumBarChart.js            ← 2-minute-binned diverging momentum bar chart
      README.md
  sample_data/
    shots_3943043.json               ← UEFA Euro 2024 Final shots
    pass_network_3943043_Spain.json
    pass_network_3943043_England.json
    freeze_frames_3943043_goals.json
    convex_hull_3943043_goals.json
    heatmap_3943043_{player_slug}.json
    match_stats_3943043.json
    formation_3943043_Spain.json
    formation_3943043_England.json
    progressive_map_3943043_Spain.json
    progressive_map_3943043_England.json
    possession_3943043_60.json
    xt_grid.json
    xt_actions_3943043.json
    momentum_3943043.json
    cumulative_xg_3943043.json
    goal_animation_3943043.json
```

## Components

| Component | File | Description |
|---|---|---|
| **pitch** | `components/pitch/pitch.js` | StatsBomb 120×80 pitch base layer. Returns `{ g, px }` for downstream components. Modes: `full` / `half`; orientations: `horizontal` / `vertical`. |
| **shotMap** | `components/shotMap/shotMap.js` | Shot scatter on a half-pitch. Circle area encodes xG; color encodes outcome. Tooltip: player / outcome / minute / xG. |
| **passNetwork** | `components/passNetwork/passNetwork.js` | Substitution-windowed directed pass network. Node size = pass count; edge thickness = pair count. Window selector synced externally. |
| **freezeFrame** | `components/freezeFrame/freezeFrame.js` | 360 freeze-frame dot overlay for a single goal instant. Encodes teammate / opponent / actor / keeper. |
| **convexHull** | `components/convexHull/convexHull.js` | Convex hull territory polygons for offense / defense at a freeze-frame instant. Sits behind the freeze-frame dot layer. |
| **heatmap** | `components/heatmap/heatmap.js` | Player on-ball KDE density surface. Shows where a player participated in play — not off-ball movement. |
| **matchStats** | `components/matchStats/matchStats.js` | Match-level stat table (shots, possession, xG, cards, …). Wraps `comparisonBars.js`. |
| **comparisonBars** | `components/comparisonBars/comparisonBars.js` | Generic home/away mirrored bar chart. Football-agnostic; consumed by matchStats and reusable. |
| **formation** | `components/formation/formation.js` | Declared formation and tactical-shift sequence with template-slot player positions. |
| **teamShape** | `components/teamShape/teamShape.js` | Empirical in-possession player nodes (on-ball) and out-of-possession density cloud (off-ball, anonymous). |
| **progressiveMap** | `components/progressiveMap/progressiveMap.js` | Progressive pass/carry arrows on the full pitch. Encodes completed/incomplete and progressive/non-progressive. |
| **eventScatter** | `components/eventScatter/eventScatter.js` | General event scatter on the pitch. Markers at (x, y); arrows for Pass/Carry/Shot. Color-coded by semantic category. |
| **timelineStrip** | `components/timelineStrip/timelineStrip.js` | Single-possession elapsed-seconds horizontal strip. Real-time axis; stacking for near-simultaneous events. Standalone chart, not a pitch overlay. |
| **xtSurface** | `components/xtSurface/xtSurface.js` | Karun Singh open xT grid rendered as a heatmap beneath pitch markings. Reads `xt_grid.json`. |
| **playAnimation** | `components/playAnimation/playAnimation.js` | Time-windowed ball-path animation with play/pause/scrub. Straight-line segments; both teams included. Composes on pitch.js. |
| **momentumChart** | `components/momentumChart/momentumChart.js` | Per-minute xT-based attacking momentum curve. Horizontal or vertical orientation; secondary window overlay; goal/card markers. |
| **cumulativeXgChart** | `components/cumulativeXgChart/cumulativeXgChart.js` | Per-team cumulative xG "race chart" — step-line per team from raw shot events, with actual-goal G-chip overlay. Horizontal or vertical orientation. |
| **momentumBarChart** | `components/momentumBarChart/momentumBarChart.js` | 2-minute-binned diverging momentum bar chart — discrete per-window bars (vs. momentumChart's smoothed curve), driven by an `onHover` callback instead of an internal tooltip. |

Full API docs, JSON contract, and usage examples in each component's `README.md`.

## Adding a new component

1. Create `components/<name>/<name>.js`. Export a function that accepts a D3
   selection (or the pitch object returned by `createPitch`) plus a config object.
2. Add a `components/<name>/README.md` covering what the component does, its JSON
   contract, and a minimal usage example (required by the documentation standard).
3. Wire it into `index.html`: add a `<section>` with a stage SVG, import the module,
   fetch the sample data, and call the render function.

## Notes

- `sample_data/` holds real StatsBomb data exported by the Python extractors in
  `libs/statsbomb/`. Never fabricate fixture data.
- This harness is for component development, not publication. A publication
  stack (Quarto / Astro / Observable) is deferred until the first analysis is
  substantively complete.
- All coordinates are StatsBomb-native 120×80 yards. Components delegate pixel
  mapping to `pitch.px()` and never transform coordinates themselves.
