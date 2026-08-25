# formation.js

Renders a declared formation diagram on a full pitch. Player markers are placed at **canonical template-slot positions** derived from StatsBomb position labels. These are the **coach's stated shape** — NOT measured from play.

## What it shows

- One formation period at a time: Starting XI or any subsequent Tactical Shift.
- Each player marker: filled circle with jersey number + display name label.
- Step through periods via `update({ periodIdx })`.
- Optionally clickable: pass `onPlayerClick` to make non-goalkeeper markers act as
  selection targets (e.g. a player-selector UI). The Goalkeeper marker is never
  clickable — it gets `cursor: default` and no click handler.
- Optionally a **selector**: pass `selectedId` (+ `update({ selectedId })`) to
  ring the currently selected player's marker (radius +5, stroke-width 2) —
  the selected node's own circle stroke also switches to `selectedColor`/2px
  (instead of `backgroundColor`/1.5px), so the node itself reads as selected,
  not just its outer ring. Combined with `onPlayerClick`, this is the app's
  one-team-at-a-time player-selector UI — team switching is the caller's
  concern (pass a different team's `data` and re-mount, or call
  `createFormation` again), not something this component owns.
- Optionally a **bench**: pass `data.bench` (that team's
  `substitutes_{match_id}.json` array) to render a clickable substitute list
  below the pitch, wrapped into `config.benchColumns` columns (default 1 — at
  the narrow pitch widths this actually renders at, e.g. a ~300px lineup-
  selector column, 2+ columns leave too little room for a surname before it
  collides with the right-aligned "on NN'" text; raise it if your container
  is wider). Same click/selection/goalkeeper rules as starter nodes. The
  selected row gets a filled background (`selectedColor` at 0.13
  fill-opacity) + border, and its text recolors to `selectedColor`;
  unselected rows show the same fill (no border) on hover. Omitting
  `data.bench` renders exactly as before — the SVG is only sized taller than
  the pitch when a bench is present, so existing read-only consumers (the
  match dashboard's `FormationPanel`) are unaffected.

## What it does NOT show

- Where players actually were during the match — that is empirical, measured data, which belongs in a separate component (`teamShape.js`).
- The formation diagram is declared intent, not observed behaviour.

## JSON contract

File: `sample_data/formation_{match_id}_{team_slug}.json`

```json
{
  "periods": [
    {
      "formation": "4-2-3-1",
      "from_minute": 0,
      "to_minute": 69,
      "players": [
        {
          "player_id": 3468,
          "player": "Jordan Pickford",
          "display_name": "Jordan Pickford",
          "jersey_number": 1,
          "position": "Goalkeeper",
          "template_x": 6.0,
          "template_y": 40.0
        }
      ]
    }
  ],
  "metadata": {
    "match_id": 3943043,
    "team": "England",
    "competition": "UEFA Euro",
    "match_label": "Spain vs England",
    "coordinate_note": "template_x and template_y are canonical formation-slot positions in StatsBomb 120×80 coordinate space. They are NOT measured from play — they represent the declared tactical shape derived from StatsBomb position labels."
  }
}
```

**Template coordinates** are authored slots in StatsBomb 120×80 yard space (team attacks left → right, increasing x). They are NOT player-tracking data and are NOT influenced by events. The mapping from StatsBomb position label to slot lives in `libs/statsbomb/formation_templates.json`.

Bench entries (`data.bench`, optional) are `substitutes_{match_id}.json`'s own
per-team array — `{ player_id, display_name, jersey_number, position, on_minute }`.
See `extract_substitutes.py`; not duplicated here since the shape is unchanged.

## Usage

```js
import { createFormation } from "./components/formation/formation.js";

// Provide an SVG element — createFormation creates the pitch internally.
const { update } = createFormation(d3.select("#formation-svg"), data, {
  pxPerYard: 7,
  theme: "whiteboard",
  nodeColor: "#1E3A5F",
});

// Step through formation periods (e.g. wired to a <select>).
update({ periodIdx: 1 }); // Tactical Shift at 69'

// One-team-at-a-time player selector: starters + bench, both clickable,
// with a ring on whichever player_id is currently selected.
const { update: selectorUpdate } = createFormation(d3.select("#formation-svg"), {
  ...formationData,
  bench: substitutesData.teams[formationData.metadata.team],
}, {
  selectedId: currentSelection,
  onPlayerClick: (player) => selectPlayer(player.player_id),
});

// Selection changes externally (e.g. the popup's close button):
selectorUpdate({ selectedId: null });
```

## Return value

```js
{ svg, g, px, update }
```

- `svg` — D3 selection of the SVG element.
- `g` — D3 selection of the pitch group; append further overlays here.
- `px(sbX, sbY) => [screenX, screenY]` — coordinate conversion from createPitch().
- `update({ periodIdx?, selectedId? })` — re-renders markers for a given period
  index (0 = Starting XI) and/or moves the selection ring. Any omitted key
  retains its current value.

## Extraction

Run `libs/statsbomb/extract_formation.py` to generate the JSON:

```sh
uv run python libs/statsbomb/extract_formation.py
```

Reads Starting XI + Tactical Shift events from StatsBomb. Maps each player's position label to a template coordinate via `libs/statsbomb/formation_templates.json`. Writes one JSON file per team.
