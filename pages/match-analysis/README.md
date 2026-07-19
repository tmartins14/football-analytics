# Match Analysis Dashboard

A standalone analysis page composing seven existing D3 components for a single match.
The default match is **Spain 2–1 England, UEFA Euro 2024 Final** (match ID 3943043).

## What it shows

Three horizontal zones, top to bottom:

**Top strip (full width)** — toggled view:
- **Goal Animation** (default): animated ball path for each goal in the match, with
  a goal-selector, play/pause, and scrubber. Uses `playAnimation.js`.
- **Shot Map**: both teams' shots on one half-pitch, with circle area ∝ xG. Uses `shotMap.js`.

**Team columns (Spain left, England right)** — each with a 3-way toggle:
- **Formation** (default): declared XI with tactical shape per lineup period. Uses `formation.js`.
- **Pass Network**: substitution-windowed directed pass network with a window selector. Uses `passNetwork.js`.
- **Team Shape**: two nested views (On-ball / Off-ball sub-toggle):
  - *On-ball*: identified player positions averaged per event, per lineup period.
    A period selector steps through substitution windows.
  - *Off-ball*: anonymous 360-frame density with centroid, ellipse, and depth line.
  Uses `teamShape.js`.

**Center column** — toggled view:
- **Match Stats** (default): comparison bars for key match statistics. Uses `matchStats.js`.
- **Momentum**: per-minute xT momentum curve with goal markers. Uses `momentumChart.js`.

## Components composed

| Component | File |
|---|---|
| `createPitch` | `components/pitch/pitch.js` |
| `createFormation` | `components/formation/formation.js` |
| `createPassNetwork` | `components/passNetwork/passNetwork.js` |
| `createTeamShape` | `components/teamShape/teamShape.js` |
| `createMatchStats` | `components/matchStats/matchStats.js` |
| `createMomentumChart` | `components/momentumChart/momentumChart.js` |
| `createPlayAnimation` | `components/playAnimation/playAnimation.js` |
| `createShotMap` | `components/shotMap/shotMap.js` |

No component files are modified — this is a pure composition layer.

## Toggle behavior

- Each toggle is **local UI state** — no cross-panel event bus or shared selection state.
- All component instances mount **once on page load** and stay mounted.
  Toggling shows/hides containers via CSS `display: none`; components remain alive.
- State resets to defaults on page reload (no `localStorage`).

## Data files

All JSON is served from `data/euro-2024/3943043/` (repo root). Filenames:

```
shots.json
pass_network_Spain.json
pass_network_England.json
match_stats.json
formation_spain.json
formation_england.json
team_shape_spain.json
team_shape_england.json
momentum.json
goal_animation.json
```

## How to run

From the repository root:

```bash
python3 -m http.server 8000
```

Then open:

```
http://localhost:8000/src/footballd3/dashboards/match-analysis/index.html
```

To extract data for additional matches, use the batch script:

```bash
uv run python scripts/extract_euro2024.py
```
