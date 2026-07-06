# xtSurface

Renders Karun Singh's published xT (Expected Threat) grid as a colored heatmap surface
beneath the pitch markings. Each of the 96 grid cells (8 rows × 12 cols) is filled with
a color encoding its xT value — light neutral at low threat, deep rose (#9F1239) at high
threat. The surface composes on `pitch.js` and is inserted beneath all pitch markings so
field lines remain visible through the color layer.

## How to interpret it

xT (Expected Threat) assigns each pitch zone a value equal to the probability that the
team in possession will score from that zone within a few actions. High values cluster
near the attacking goal (right side on a horizontal pitch). Darker cells = higher scoring
threat from that location.

A ball-progression action's xT contribution is `grid_value(end_zone) − grid_value(start_zone)`.
Positive = threat gained (ball moved into a more dangerous zone). Negative = threat lost
(ball moved backward or laterally into a safer zone). Per-action deltas are in the
companion `xt_actions_{match_id}.json` file; this component renders the grid surface
only.

## Grid provenance — read this

**Grid source:** Karun Singh's published open xT grid (`open_xt_12x8_v1`), trained on
**his own match corpus — NOT StatsBomb data and NOT Euro 2024.**

The grid values are **transferred**, not fitted to this dataset. Absolute xT values are
directionally meaningful (zones near goal score higher than deep zones) but are **not
calibrated to Euro 2024**. Do not cite these values as Euro 2024 estimates.

Karun's original blog post ([karun.in/blog/expected-threat](https://karun.in/blog/expected-threat))
describes a 16×12 grid; `open_xt_12x8_v1` (8 rows × 12 cols, 96 cells) is the only
standalone published JSON he has released.

## Which actions are credited

Per-action xT deltas (in `xt_actions_{match_id}.json`) are computed only for:

- **Completed open-play passes** — `type == "Pass"`, `pass_outcome` is null (null = complete
  in StatsBomb encoding), `play_pattern` not in the set-piece filter.
- **Open-play carries** — `type == "Carry"`, `play_pattern` not in the set-piece filter.
  Carries are always completed: StatsBomb has no incomplete-carry event.

**Excluded:**
- Shots — they are the terminal reward the grid is built from, not a credited progression move.
- Incomplete passes — possession was lost; no xT credit awarded.
- Set pieces — `play_pattern` in `{From Corner, From Free Kick, From Goal Kick, From Kick Off, From Throw In}`.

## Coordinate mapping (StatsBomb → grid cell)

StatsBomb coordinates: `x ∈ [0, 120]`, `y ∈ [0, 80]` yards. Grid: 8 rows (Y) × 12 cols (X).

| Dimension | Formula | Result range |
|-----------|---------|-------------|
| col (X zone) | `min(floor(x / 120 × 12), 11)` | 0 (defensive) → 11 (attacking) |
| row (Y zone) | `min(floor(y / 80 × 8), 7)` | 0 (y≈0 touchline) → 7 (y≈80 touchline) |

Boundary rule: exact upper-bound coordinates (`x=120`, `y=80`) are clamped to the last
valid cell index. Mapping is purely proportional — no physical pitch dimensions assumed.

StatsBomb normalizes all events so the team in possession always attacks toward `x → 120`.
No direction flip is applied; the lookup is direct for both teams.

## JSON contracts

### `xt_grid.json` (input to this component)

```json
{
  "rows": 8,
  "cols": 12,
  "values": [[0.00638, ...], ...],
  "source": "Karun Singh open_xt_12x8_v1",
  "source_url": "https://karun.in/blog/data/open_xt_12x8_v1.json",
  "pitch_dims": { "width_yards": 120, "height_yards": 80 },
  "cell_dims": { "width_yards": 10.0, "height_yards": 10.0 }
}
```

`values[row][col]` — row indexes Y-zone (0 = y≈0 touchline, 7 = y≈80 touchline),
col indexes X-zone (0 = defensive end, 11 = attacking end).

### `xt_actions_{match_id}.json` (companion, for downstream use)

```json
{
  "actions": [
    {
      "event_id": "uuid",
      "team": "Spain",
      "display_name": "Pedri",
      "minute": 23,
      "second": 41,
      "x0": 45.2, "y0": 32.1,
      "x1": 67.8, "y1": 29.4,
      "start_zone": [3, 4],
      "end_zone": [3, 6],
      "xt_delta": 0.00324,
      "action_type": "Pass"
    }
  ],
  "metadata": {
    "match_id": 3943043,
    "competition": "UEFA Euro",
    "season": "2024",
    "match_label": "Spain vs England",
    "grid_source": "Karun Singh open_xt_12x8_v1",
    "grid_dims": [8, 12],
    "n_actions": 685
  }
}
```

`start_zone` / `end_zone` are `[row, col]`. Native StatsBomb coordinates preserved as
`x0/y0/x1/y1`. `second` is the in-minute second from the StatsBomb `second` column.

## Usage example

```javascript
import { createPitch }     from "../pitch/pitch.js";
import { createXtSurface } from "./xtSurface.js";

Promise.all([
  fetch("../../sample_data/xt_grid.json").then(r => r.json()),
]).then(([gridData]) => {
  const pitch = createPitch(d3.select("#xt-svg"), {
    mode:        "full",
    orientation: "horizontal",
    pxPerYard:   7,
    theme:       "whiteboard",
  });

  const { g, update } = createXtSurface(pitch, gridData, {
    opacity: 0.65,
  });

  // Adjust opacity at runtime
  document.getElementById("opacity-slider").addEventListener("input", function () {
    update({ opacity: +this.value });
  });
});
```

## Extraction

```bash
uv run python src/statsbomb/extract_xt.py
# → src/footballd3/sample_data/xt_grid.json
# → src/footballd3/sample_data/xt_actions_3943043.json
```
