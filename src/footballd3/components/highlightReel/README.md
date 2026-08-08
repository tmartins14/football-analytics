# highlightReel.js

Compact play/step reel of one player's standout moments: play/step controls,
a big minute readout, the current moment's kind + description, and clickable
progress dots. Moment selection is entirely client-side — no dedicated
extractor.

## Moment selection

`selectMoments(events)` (a named export, independently testable/reusable) —
computed once per player, not reactive to the current scrub position (the
reel always considers the whole match):

1. Every goal (`is_goal`) — `"Goal · xG {shot_xg}"`.
2. The single highest-`shot_xg` non-goal Shot, if any — `"Shot · xG {shot_xg} · {outcome}"`.
3. The top 3 **positive**-`xt_delta` Pass/Carry events (not top-`|xt_delta|`
   — negative swings never qualify) — `"{Progressive }{type} · +{xt_delta} xT"`.

The combined set is sorted by minute ascending and capped at 5. This is a
plain chronological truncation with **no goal-priority protection**: with
more than 5 combined candidates, the latest-occurring ones are dropped even
if one of them is a goal.

## This component does not own the scrubber

`scrubbedMinute` has exactly one writer in the app's state model: the master
scrubber (`scrubber.js`). `highlightReel.js` never calls a scrubber directly
— it only reports "move to this minute" via `onScrubTo(minute)`. The
consuming panel is responsible for calling the scrubber's own `seek()` in
response, exactly as it would for a direct drag. This keeps the
single-writer invariant intact even though playback is driven from a second
component.

## Play vs. step

- **Play**: jumps straight to the first moment's minute (no separate reset
  step), then advances through the rest at `stepDurationMs` intervals
  (default 1800ms), stopping once the last moment is reached — it does not
  loop. Clicking Play again while playing stops it — the same button and
  handler drive both states, label toggles `"▶ Play"` / `"❚❚ Stop"`.
- **Step** (prev/next buttons, or clicking a dot): stops any running
  playback, moves the current index by one (or jumps to the clicked dot),
  and fires `onScrubTo` immediately.

## JSON contract (consumed)

Same `player_events/{match_id}/{player_id}.json` shape every other panel
reads — pass the **full match**, not a scrub-filtered slice. The reel always
selects from every credited event regardless of the current scrub position;
only playback moves the scrubber, not the other way around.

## Usage

```js
import { createHighlightReel } from "./highlightReel.js";

const { play, pause, step } = createHighlightReel(d3.select("#reel-container"), data, {
  stepDurationMs: 1800,
  onScrubTo: (minute) => scrubber.seek(minute),
  onHoverEvent: (eventId) => {
    // eventId or null — cross-highlight the matching pitch marker/xT point/feed row.
  },
});
```

## Returns

`{ container, update, play, pause, step }`:

- `container` — the reel's root D3 selection.
- `update({ data? })` — re-renders with a new events array (re-selects
  moments, resets to index 0, stops any active playback).
- `play()` — begin playback (or stop it, if already playing).
- `pause()` — stop playback without changing the current index.
- `step(delta)` — stop any playback and move the current index by `delta`
  (e.g. `1` or `-1`), clamped to the moment list, firing `onScrubTo`
  immediately.

## Config reference

| Option | Default | Description |
|--------|---------|-------------|
| `stepDurationMs` | `1800` | Milliseconds between moments during Play |
| `teamColor` | — | Accepted for API-shape parity with the design spec, but intentionally unused — every reel color comes from the tokens below, not the player's team color |
| `onScrubTo` | `null` | `onScrubTo(minute)` — fires on every step (Play advancing, or a manual prev/next/dot click) |
| `onHoverEvent` | `null` | `onHoverEvent(eventId \| null)` — fires on hover/unhover of the current moment's description |
| `borderColor` | `"#E5E5E5"` | Prev/next button border |
| `buttonBackground` | `"#FFFFFF"` | Prev/next button fill |
| `textColor` | `"#171717"` | Body text color |
| `faintColor` | `"#8A8578"` | Label/empty-state text color |
| `focalColor` | `"#9F1239"` | Accent — minute readout, Play button fill, active dot |
| `focalTextColor` | `"#FAF7F0"` | Text color on the (always-filled) Play button — pass the theme's own background color |
| `inactiveDotColor` | `"#D6D3CC"` | Inactive progress dot fill |

## Extraction

No dedicated extractor — reads `extract_player_events.py`'s output directly
and selects moments client-side, same as `passSonar.js` and `actionFeed.js`.
