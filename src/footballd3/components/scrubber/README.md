# scrubber.js

Master minute-scrubber for driving a cross-component match view. Renders a
horizontal 0–maxMinute track with a draggable playhead; every interaction calls
`config.onScrub(minute)`.

This component does **not** compose on `pitch.js` — it is a standalone temporal
control, not a spatial overlay.

## What it is (and isn't)

`scrubber.js` is a **controller**, not a display. It owns no rendering logic for
match data itself — it only reports "the scrubbed minute changed" so sibling
components (a heatmap, an event scatter, a territory hull, a cumulative-xT line,
…) can filter or update themselves in response. All of those sibling components
read the same underlying event data and apply their own `minute <= scrubbedMinute`
predicate; `scrubber.js` never touches that data beyond the optional density-hint
ticks described below.

## Why a new component instead of extending timelineStrip.js

`timelineStrip.js`'s whole purpose is narrative tempo **within one possession** —
a real elapsed-seconds axis sized for a handful of events, with a documented
**read-only** future-linkage design (its `xScale` is exposed so a sibling can read
a position from it, not so it can drive others). A 0–90+-minute master scrubber
that **writes** to five sibling components via `onScrub` is a different domain
scale (minutes, not seconds; a whole match/player window, not one possession) and
a different responsibility (controller, not narrative display). Conflating the two
would double `timelineStrip.js`'s branching for two genuinely different concerns
and risks regressing its existing possession-level usage elsewhere in the gallery.
`timelineStrip.js` is untouched by this component.

## Density hints

Passing an `events` array (any objects with a `minute` field — e.g. a player's
event stream) draws light tick marks at each event's minute along the track. This
is purely a visual density hint — `scrubber.js` reads only the `minute` field and
does not filter, interpret, or otherwise analyze the events.

## Interaction

- **Drag** the handle.
- **Click** anywhere on the track to jump to that minute.
- **Arrow keys** (when the handle has focus): `ArrowLeft`/`ArrowRight` for
  1-minute steps, `Shift+ArrowLeft`/`Shift+ArrowRight` for 5-minute steps.

Every move — drag, click, or key — calls `onScrub(minute)`.

## Usage

```js
import { createScrubber } from "./scrubber.js";

const { seek, update } = createScrubber(d3.select("#scrubber-container"), {
  width: 760,
  minMinute: 0,
  maxMinute: 94,
  initialMinute: 94,
  events: playerEvents,        // optional density-hint ticks
  onScrub: (minute) => {
    // Drive sibling components, e.g.:
    heatmapController.update(checkpointForMinute(minute));
    eventScatterController.update({ filter: e => e.minute <= minute });
  },
});

// Later: swap in a different player's events for the density ticks.
update({ events: nextPlayerEvents });

// Programmatic move without firing onScrub (e.g. initial sync from external state).
seek(70);
```

## Returns

`{ svg, g, xScale, update, seek }`:

- `svg` — the created SVG selection.
- `g` — the main `<g>` group.
- `xScale` — `d3.scaleLinear` mapping minute → pixels.
- `update({ events? })` — replace the density-hint event array and re-render the ticks.
- `seek(minute)` — move the playhead programmatically **without** firing `onScrub`.

## Notes

- **No JSON extraction step.** Unlike most `footballd3` components, `scrubber.js`
  has no dedicated Python extractor or sample-data file — it's a generic control
  driven by whatever event data a consuming view already has loaded (e.g. the
  `player_events/{match_id}/{player_id}.json` contract from
  `extract_player_events.py`).
- **Clamped domain.** `xScale` is created with `.clamp(true)`; drag/click positions
  outside `[minMinute, maxMinute]` snap to the nearest bound.
