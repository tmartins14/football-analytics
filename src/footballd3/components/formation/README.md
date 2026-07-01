# formation.js

Renders a declared formation diagram on a full pitch. Player markers are placed at **canonical template-slot positions** derived from StatsBomb position labels. These are the **coach's stated shape** — NOT measured from play.

## What it shows

- One formation period at a time: Starting XI or any subsequent Tactical Shift.
- Each player marker: filled circle with jersey number + display name label.
- Step through periods via the `update(periodIdx)` method.

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

**Template coordinates** are authored slots in StatsBomb 120×80 yard space (team attacks left → right, increasing x). They are NOT player-tracking data and are NOT influenced by events. The mapping from StatsBomb position label to slot lives in `src/statsbomb/formation_templates.json`.

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
update(1); // Tactical Shift at 69'
```

## Return value

```js
{ svg, g, px, update }
```

- `svg` — D3 selection of the SVG element.
- `g` — D3 selection of the pitch group; append further overlays here.
- `px(sbX, sbY) => [screenX, screenY]` — coordinate conversion from createPitch().
- `update(periodIdx)` — re-renders markers for the given period index (0 = Starting XI).

## Extraction

Run `src/statsbomb/extract_formation.py` to generate the JSON:

```sh
uv run python src/statsbomb/extract_formation.py
```

Reads Starting XI + Tactical Shift events from StatsBomb. Maps each player's position label to a template coordinate via `src/statsbomb/formation_templates.json`. Writes one JSON file per team.
