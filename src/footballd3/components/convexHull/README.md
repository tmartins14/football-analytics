# convexHull

Renders convex hull territory polygons for both teams at a single freeze-frame instant.
Overlay component: draws semi-transparent hull polygons on top of an existing
pitch + freeze-frame render without re-rendering the pitch or player dots.

---

## What it shows

At a single 360-degree freeze-frame event (one instant in the match), each team's visible
outfield players form a convex hull — the smallest convex polygon that encloses all of
them. This gives a rough territorial footprint at that moment.

"Offense" is the team in possession at the moment of the event (resolved from
`possession_team_id`). "Defense" is the other team. These are structural labels derived
from the event metadata, not a judgment about which team is literally attacking.

---

## Critical limitations — read before interpreting hull area

**1. Visible players only.**
StatsBomb 360 data captures a broadcast camera view framed around the ball. The hull
encloses only the players visible on screen at that instant, not every player on the
pitch. Hull area is not reliably comparable frame-to-frame because the visible set
changes as the camera reframes.

**2. Asymmetric team sampling.**
Because the camera frames around the ball, the two teams are usually captured to
different completeness in the same frame — the team near the ball has more players
visible than the team farther away. Comparing offense vs defense hull areas is therefore
comparing two differently-complete samples. Use hull shape and position to understand
spatial structure; do not treat the area ratio as a territory scoreboard.

**3. Keeper excluded by design.**
The goalkeeper is excluded from hull computation. A keeper positioned far from the
outfield group (typical positioning) would balloon the hull into unoccupied dead space
and make the polygon uninterpretable. The keeper marker remains visible from the
underlying freeze-frame layer. The `includeKeeper` flag in the hull metadata records
whether keepers were included at extraction time (default: `false`).

**4. Convex hulls overstate occupied territory.**
When one player is separated from the rest of the group, the hull encloses the
unoccupied space between them. This is a known property of convex hulls, not a bug.
A concave/alpha-shape variant would better follow the actual player distribution and
is a noted future option.

---

## JSON contract

Input: one entry from `sample_data/convex_hull_{match_id}_goals.json → hulls[]`

```json
{
  "sides": [
    {
      "side": "offense",
      "team_name": "Spain",
      "hull_vertices": [[111.5, 47.1], [109.7, 32.4], [108.2, 36.8]],
      "area": 49.14,
      "player_count": 4
    },
    {
      "side": "defense",
      "team_name": "England",
      "hull_vertices": [[105.1, 28.9], [113.4, 31.2], [114.0, 48.3], [110.6, 53.5], [104.8, 44.0]],
      "area": 67.11,
      "player_count": 6
    }
  ],
  "metadata": {
    "match_id": 3943043,
    "event_id": "bf03dfcf-f281-4646-98de-620649a1308b",
    "minute": 46,
    "possession_team_name": "Spain",
    "actor_team_name": "Spain",
    "include_keeper": false
  }
}
```

- `hull_vertices` — ordered convex hull vertices in StatsBomb-native 120×80 yards.
  D3 maps them to screen space via `pitch.px()`.
- `area` — enclosed area in square yards (scipy `ConvexHull.volume` in 2-D equals area).
- `player_count` — number of outfield players used for hull computation (keeper-excluded
  unless `include_keeper: true`).
- A `sides` entry is **omitted** when fewer than 3 outfield players are visible
  (degenerate hull — collinear or singleton case).

The top-level file structure:
```json
{
  "hulls": [ ... ],
  "match_metadata": { "match_id": int, "competition": str, "match_label": str }
}
```

`hulls[]` is parallel to `goals[]` in `freeze_frames_{match_id}_goals.json`; pair by
`metadata.event_id`.

---

## Offense / defense resolution

Python determines offense and defense from the event's `possession_team`:

```
actor_side   = frame players where teammate == True   (includes the actor)
opponent_side = frame players where teammate == False

if actor_team == possession_team:
    offense = actor_side
    defense  = opponent_side
else:
    offense = opponent_side
    defense  = actor_side
```

The `teammate` boolean in StatsBomb 360 data is relative to the **actor** (the player
who performed the event), not to a fixed team. The code explicitly compares `actor_team`
to `possession_team` rather than assuming the actor is always on the offensive side.

---

## Usage

```javascript
import { createPitch }       from "../pitch/pitch.js";
import { createFreezeFrame } from "../freezeFrame/freezeFrame.js";
import { createConvexHull }  from "../convexHull/convexHull.js";

// Shared hull config: mirrorX must match the freeze-frame mirrorX.
const mirrorX = true;

const pitch = createPitch(d3.select("#svg"), {
  mode: "half", orientation: "vertical", pxPerYard: 7,
});

// Freeze frame draws player dots.
const ff = createFreezeFrame(pitch, frameData, { mirrorX });

// Convex hull draws territory polygons behind the dots (auto-inserts before .ff).
const ch = createConvexHull(pitch, hullEntry, {
  toggle:       "both",         // "offense" | "defense" | "both"
  offenseColor: "#9F1239",
  defenseColor: "#1E3A5F",
  mirrorX,
});
```

`createConvexHull` can be called before or after `createFreezeFrame` — it auto-inserts
its `<g class="ch">` before the `<g class="ff">` group so hulls always render behind dots.

### Config options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `toggle` | string | `"both"` | Which hull(s) to render: `"offense"`, `"defense"`, or `"both"` |
| `offenseColor` | string | `"#9F1239"` | Fill and stroke color for the offense hull |
| `defenseColor` | string | `"#1E3A5F"` | Fill and stroke color for the defense hull |
| `fillOpacity` | number | `0.18` | Hull fill opacity |
| `strokeOpacity` | number | `0.55` | Hull stroke opacity |
| `strokeWidth` | number | `1.5` | Hull stroke width in px |
| `mirrorX` | boolean | `false` | Mirror x as `120-x` before `px()`. Must match the `mirrorX` value passed to `createFreezeFrame()` |

### Return value

```js
{ g: d3.Selection, px: Function }
// g  — the <g class="ch"> group in pitch.g
// px — the coordinate mapper (pitch.px, with optional mirrorX wrapping)
```

---

## Extraction

```bash
uv run python src/statsbomb/extract_convex_hull.py
```

Resolves the UEFA Euro 2024 Final match ID live via the StatsBomb API, loads 360 frames
(with GitHub raw JSON fallback for statsbombpy ≤ 1.18), computes hulls for all goal
events, and writes:

```
src/footballd3/sample_data/convex_hull_{match_id}_goals.json
```

Dependencies: `scipy>=1.12` (added to `pyproject.toml`), `numpy`, `statsbombpy`, `pandas`.
