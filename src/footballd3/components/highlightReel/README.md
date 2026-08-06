# highlightReel.js

Compact play/step reel of one player's standout moments: play/step controls,
the current moment's minute + a short annotation, and clickable progress
dots. Moment selection is entirely client-side for v1 — no dedicated
extractor.

## Moment selection

`selectMoments(events, maxMoments = 5)` (a named export, independently
testable/reusable): every goal first (chronological order), then the
highest-`|xt_delta|` Pass/Carry actions filling any remaining slots up to
`maxMoments`, with the whole set re-sorted chronologically for display. A
player with fewer than 3 qualifying events simply gets fewer moments — there
is no padding.

## This component does not own the scrubber

`scrubbedMinute` has exactly one writer in the app's state model: the master
scrubber (`scrubber.js`). `highlightReel.js` never calls a scrubber directly
— it only reports "move to this moment" via `onMoment(moment, index)` and
"reset to the start" via `onReset()`. The consuming panel is responsible for
calling the scrubber's own `seek()` in response, exactly as it would for a
direct drag. This keeps the single-writer invariant intact even though
playback is driven from a second component.

## Play vs. step

- **Play**: `onReset()` fires once, then `onMoment` fires for index 0, 1, 2,
  ... at `stepDurationMs` intervals (default 1800ms, matching the design
  spec's "~1.8s each"), stopping after the last moment — it does not loop.
- **Step** (prev/next buttons, or clicking a dot): does **not** reset
  anything — it just moves the current index by one (or jumps to the clicked
  dot) and fires `onMoment` immediately, for scrubbing through moments
  without replaying the whole build-up each time.

## JSON contract (consumed)

Same `player_events/{match_id}/{player_id}.json` shape every other panel
reads — pass the **full match**, not a scrub-filtered slice. The reel always
selects from every credited event regardless of the current scrub position;
only playback moves the scrubber, not the other way around.

## Usage

```js
import { createHighlightReel } from "./highlightReel.js";

const { play, pause, step } = createHighlightReel(d3.select("#reel-container"), data, {
  maxMoments: 5,
  stepDurationMs: 1800,
  onReset: () => scrubber.seek(0),
  onMoment: (moment) => scrubber.seek(moment.minute),
});
```

## Returns

`{ container, update, play, pause, step }`:

- `container` — the reel's root D3 selection.
- `update({ data? })` — re-renders with a new events array (re-selects
  moments, resets to index 0, stops any active playback).
- `play()` — begin playback from the start.
- `pause()` — stop playback without changing the current index.
- `step(delta)` — move the current index by `delta` (e.g. `1` or `-1`),
  clamped to the moment list, firing `onMoment` immediately.

## Config reference

| Option | Default | Description |
|--------|---------|-------------|
| `maxMoments` | `5` | Upper bound on selected moments |
| `stepDurationMs` | `1800` | Milliseconds between moments during Play |
| `onReset` | `null` | `onReset()` — fires once when Play begins |
| `onMoment` | `null` | `onMoment(moment, index)` — fires on every step |

## Extraction

No dedicated extractor — reads `extract_player_events.py`'s output directly
and selects moments client-side, same as `passSonar.js` and `actionFeed.js`.
