# goalMouthShotPanel.js

Goal-frame view of one player's shots — **not a pitch**, distinct from
`shotMap.js` (which plots shot *origin* on a half-pitch). This plots shot
*end point* relative to the goal mouth: on-target shots inside the frame,
off-target shots in a labelled zone above the crossbar. Radius encodes
`shot_xg`; goals are filled and ringed, off-target shots are dashed.

## Goal frame geometry

A regulation goal is 8 yards wide, centered on the pitch's y midpoint (40),
so its posts sit at y=36 and y=44 in StatsBomb's 120×80 coordinate space.
Height uses a standard 8ft crossbar (~2.67 StatsBomb yards). These are fixed
constants — StatsBomb doesn't vary goal geometry per match.

## On-target / off-target classification

Uses the Shot event's own `outcome` string (the same field every other panel
reads via `extract_player_events.py`) rather than re-deriving it from
`shot_end_location`'s coordinates:

- **On-target:** `"Goal"`, `"Saved"`
- **Off-target:** everything else credited as a shot (`"Off T"`, `"Post"`,
  `"Blocked"`, `"Wayward"`, ...)

## Off-target placement is symbolic, not a true trajectory plot

A blocked shot's `shot_end_location` is the block point (often nowhere near
the goal line), and a wide/over shot's end location is only sometimes a clean
goal-line crossing point. Off-target shots are placed in a fixed strip above
the crossbar, horizontally positioned by `shot_end_location`'s y (clamped to
the strip's width) — the honest claim is "this shot missed, roughly to this
side," not "the ball crossed exactly here."

## Net visual

The frame is drawn to read as an actual goal net, not a bordered box:
a diagonal-crosshatch `<pattern>` mesh fills the frame interior (and two
receding side wedges, for depth) behind the posts/crossbar, which are drawn
last with a thicker rounded stroke on top; a ground line + soft shadow sit
beneath. Purely visual — shot placement/classification logic is untouched.
Each mounted instance gets its own `<pattern>` id (`gmsp-net-{n}`) so two
panels on the same page never collide via SVG's document-wide `url(#id)`
resolution.

## JSON contract (consumed)

Same `player_events/{match_id}/{player_id}.json` shape every other panel
reads. Non-Shot events and shots without a `shot_end_location` are ignored,
so callers may pass the full unfiltered file.

```json
{
  "events": [
    { "event_id": "...", "type": "Shot", "minute": 72, "outcome": "Goal",
      "shot_xg": 0.32, "shot_end_location": [120.0, 40.1, 1.8], "is_goal": true },
    { "event_id": "...", "type": "Shot", "minute": 55, "outcome": "Off T",
      "shot_xg": 0.05, "shot_end_location": [121.0, 46.5, 3.1], "is_goal": false }
  ]
}
```

`shot_end_location` is StatsBomb's full-pitch `[x, y, z]` triple, the same
shape as every other `end_location` field — **not** pre-collapsed to
goal-mouth `[y, z]`. This panel reads index `[1]` for goal-mouth y and index
`[2]` for height z; index `[0]` (pitch x) is unused here since on-target
shots cluster near x=120 by definition. `z` defaults to 0 when only `[x, y]`
is present.

## Usage

```js
import { createGoalMouthShotPanel } from "./goalMouthShotPanel.js";

const { update } = createGoalMouthShotPanel(d3.select("#shots-container"), data, {
  width: 320,
  height: 220,
  onHover: (eventId) => {
    // eventId or null — cross-highlight the matching pitch marker/xT point/feed row.
  },
});

update({
  data: { events: playerEvents.filter((e) => e.minute <= scrubbedMinute) },
  highlightEventId: hoveredEventId,
});
```

## Returns

`{ svg, g, update }`:

- `svg` — the created SVG selection.
- `g` — the main `<g>` group.
- `update({ data?, highlightEventId? })` — re-renders with new events and/or
  moves the inbound highlight ring. Any omitted key retains its current value.

## Config reference

| Option | Default | Description |
|--------|---------|-------------|
| `width` | `320` | SVG width in pixels |
| `height` | `220` | SVG height in pixels |
| `minRadius` / `maxRadius` | `4` / `22` | Shot-marker radius range (sqrt-scaled by `shot_xg` for area-fair sizing) |
| `frameColor` | `"#1E3A5F"` | Goal-frame stroke color |
| `onTargetColor` | `"#525252"` | On-target shot fill/stroke color |
| `goalColor` | `"#9F1239"` | Goal fill + ring color |
| `highlightColor` | `"#F59E0B"` | Inbound cross-link ring color |
| `highlightEventId` | `null` | Inbound cross-link — rings the shot with this `event_id` |
| `onHover` | `null` | `onHover(eventId \| null)` on shot hover/unhover |
| `showTooltip` | `true` | Render the built-in floating tooltip (minute, outcome, xG) |
| `showLegend` | `true` | Render the on/off/xG-radius legend |

## Extraction

No dedicated extractor — reads `extract_player_events.py`'s `shot_xg`,
`shot_end_location`, and `is_goal` fields directly (added specifically for
this panel — see that module's docstring).
