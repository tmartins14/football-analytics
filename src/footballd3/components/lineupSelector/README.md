# lineupSelector.js

Dual-team selectable formation + bench, on **one** pitch. `formation.js`
renders one team's declared shape across the *full* pitch length — correct
for a single-team diagram, but two `formation.js` instances can't share one
pitch without overlapping at midfield. This component instead creates a
single full vertical pitch (via `pitch.js`) and compresses each team's own
`template_x` into half of the shared pitch, so both teams meet at the
halfway line instead of overlapping.

## Coordinate compression

```
topTeam:    fieldX = (template_x / 120) * 60       -> range [0, 60]
bottomTeam: fieldX = 120 - (template_x / 120) * 60  -> range [60, 120]
```

`template_x` is each team's own attacking axis (0 = own goal, 120 =
opponent goal) — unchanged from `formation.js`'s contract. With the pitch's
default (non-flipped) vertical orientation, increasing `fieldX` moves *down*
the screen, so:

- the top team's keeper (`template_x=0`) sits at the very top, attacking
  down toward the halfway line (`fieldX=60`);
- the bottom team's keeper sits at the very bottom, attacking up toward the
  halfway line.

`template_y` (0-80, lateral position) is used as-is for both teams — no
compression needed on that axis. No changes to `pitch.js` or `formation.js`
were needed; this composes on `pitch.js` exactly like `convexHull.js` does.

## Goalkeepers are never selectable

Same rule as `formation.js`, for a stronger reason here: this feature's
entire data pipeline (`extract_substitutes.get_eligible_players`,
`extract_player_events.py`, `extract_player_match_summary.py`) explicitly
excludes goalkeepers as "not eligible" — no `player_events`/summary file
exists for one. Making a keeper node clickable would select a player with no
data to show.

## JSON contracts (consumed)

Three inputs, passed together as `data`:

- `top` / `bottom` — `formation_{match_id}_{team_slug}.json`'s own shape
  (from `extract_formation.py`). Only `periods[0]` (Starting XI) is used —
  this is a lineup selector, not a tactical-shift viewer.
- `bench` — `substitutes_{match_id}.json`'s own shape (from
  `extract_substitutes.py`), `{ teams: { [teamName]: [...] } }`, keyed by
  each team's `team` name (must match `data.top.team` / `data.bottom.team`).

## Usage

```js
import { createLineupSelector } from "./lineupSelector.js";

const { update } = createLineupSelector(d3.select("#lineup-svg"), {
  top: englandFormation,     // { team: "England", periods: [...] }
  bottom: spainFormation,    // { team: "Spain", periods: [...] }
  bench: substitutes,        // { teams: { England: [...], Spain: [...] } }
}, {
  topColor: "#1E3A5F",
  bottomColor: "#9F1239",
  selectedId: currentSelection,
  onSelect: (playerId, team) => selectPlayer(playerId, team),
});

// Selection changes externally (e.g. the popup's close button):
update({ selectedId: null });
```

## Returns

`{ svg, g, update }`:

- `svg` — the SVG element.
- `g` — the pitch group; the bench list is a sibling `<g>` positioned below it.
- `update({ selectedId? })` — moves the active-selection ring without a full
  re-render of formation/bench geometry.

## Config reference

| Option | Default | Description |
|--------|---------|-------------|
| `pxPerYard` | `4.4` | Pixels per StatsBomb yard |
| `padding` | `20` | Padding around the pitch in pixels |
| `theme` | `"whiteboard"` | Pitch theme |
| `topColor` | `"#1E3A5F"` | Top team node fill color |
| `bottomColor` | `"#9F1239"` | Bottom team node fill color |
| `labelColor` | `"#171717"` | Surname/bench label color |
| `selectedColor` | `"#F59E0B"` | Active-selection ring color |
| `selectedId` | `null` | Currently selected `player_id` |
| `onSelect` | `null` | `onSelect(playerId, team)` on any non-goalkeeper starter node or bench row click |

## Extraction

No dedicated extractor — reads `extract_formation.py`'s and
`extract_substitutes.py`'s existing output directly; no data-gap work was
needed for this component.
