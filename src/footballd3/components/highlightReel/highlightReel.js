/**
 * highlightReel.js — compact play/step reel of one player's standout moments.
 *
 * A single row: play/step controls, the current moment's minute + a short
 * annotation, and progress dots (one per moment, clickable). Moment selection
 * is entirely client-side for v1 (no dedicated extractor) — see selectMoments().
 *
 * THIS COMPONENT DOES NOT OWN THE SCRUBBER
 * Per the app's state model, `scrubbedMinute` has exactly one writer: the
 * master scrubber (scrubber.js). highlightReel.js never calls a scrubber
 * directly — it only reports "move to this moment" via onMoment(moment,
 * index) and "reset to the start" via onReset(). The consuming panel is
 * responsible for calling the scrubber's own seek()/onScrub() in response,
 * exactly as it would for a direct drag. This keeps the single-writer
 * invariant intact even though playback is driven from a second component.
 *
 * PLAY VS STEP
 * Play (config.onReset(), then onMoment for index 0, 1, 2, ... at
 * config.stepDurationMs intervals, stopping after the last moment — it does
 * not loop) is a full replay from kickoff. The step buttons (prev/next) do
 * NOT reset anything — they just move the current index by one and fire
 * onMoment immediately, for scrubbing through moments without replaying the
 * whole build-up each time.
 */

const DEFAULT_MAX_MOMENTS = 5;
const MIN_MOMENTS = 3;
const DEFAULT_STEP_MS = 1800;

/**
 * Auto-select 3-5 standout moments from a player's events: every goal first
 * (chronological), then the highest-|xt_delta| Pass/Carry actions filling
 * any remaining slots up to maxMoments, all re-sorted chronologically for
 * display.
 *
 * @param {Array<Object>} events - Full player_events array.
 * @param {number} maxMoments - Upper bound on selected moments.
 * @returns {Array<{ eventId: string, minute: number, second: number,
 *   annotation: string, event: Object }>} Chronologically ordered moments,
 *   min(events.length, maxMoments) long (fewer than MIN_MOMENTS only when
 *   the player has fewer than MIN_MOMENTS events at all).
 */
export function selectMoments(events, maxMoments = DEFAULT_MAX_MOMENTS) {
  const goals = events
    .filter((e) => e.type === "Shot" && e.is_goal)
    .slice(0, maxMoments);
  const goalIds = new Set(goals.map((e) => e.event_id));

  const remainingSlots = Math.max(0, maxMoments - goals.length);
  const topActions = events
    .filter((e) => (e.type === "Pass" || e.type === "Carry") && typeof e.xt_delta === "number")
    .filter((e) => !goalIds.has(e.event_id))
    .sort((a, b) => Math.abs(b.xt_delta) - Math.abs(a.xt_delta))
    .slice(0, remainingSlots);

  const selected = [...goals, ...topActions]
    .sort((a, b) => (a.minute * 60 + a.second) - (b.minute * 60 + b.second));

  return selected.map((event) => ({
    eventId: event.event_id,
    minute: event.minute,
    second: event.second,
    annotation: annotate(event),
    event,
  }));
}

/**
 * Short human-readable annotation for one moment.
 *
 * @param {Object} event - One player_events event.
 * @returns {string} e.g. "Goal", "Progressive pass +0.08 xT", "Carry -0.02 xT".
 */
function annotate(event) {
  if (event.type === "Shot" && event.is_goal) return "Goal";
  const sign = (event.xt_delta ?? 0) >= 0 ? "+" : "";
  const label = event.type === "Pass" ? "Pass" : "Carry";
  return `${label} ${sign}${(event.xt_delta ?? 0).toFixed(2)} xT`;
}

/**
 * Render a highlight reel for one player.
 *
 * @param {d3.Selection} selection - D3 selection of the container element
 *   (an HTML element — this component renders div children, not an SVG root).
 * @param {Object} data - Object with an `events` array — the
 *   player_events/{match_id}/{player_id}.json contract (full match, not
 *   scrub-filtered — the reel always selects from every credited event
 *   regardless of the current scrub position).
 * @param {Object} [config={}] - Rendering and behavior options.
 * @param {number}   [config.maxMoments=5]     - Upper bound on selected moments.
 * @param {number}   [config.stepDurationMs=1800] - Milliseconds between
 *   moments during Play.
 * @param {Function|null} [config.onReset=null]  - onReset() fires once when
 *   Play begins, before the first moment.
 * @param {Function|null} [config.onMoment=null] - onMoment(moment, index)
 *   fires on every step (Play advancing, or a manual prev/next/dot click).
 * @returns {{ container: d3.Selection, update: Function, play: Function,
 *   pause: Function, step: Function }}
 *   container — the reel's root D3 selection.
 *   update({ data? }) — re-render with a new events array (re-selects moments,
 *     resets to index 0, stops any active playback).
 *   play() — begin playback from the start.
 *   pause() — stop playback without changing the current index.
 *   step(delta) — move the current index by delta (e.g. 1 or -1), clamped to
 *     the moment list, firing onMoment immediately.
 */
export function createHighlightReel(selection, data, config = {}) {
  const {
    maxMoments = DEFAULT_MAX_MOMENTS,
    stepDurationMs = DEFAULT_STEP_MS,
    onReset = null,
    onMoment = null,
  } = config;

  const container = selection.append("div")
    .attr("class", "highlight-reel")
    .style("display", "flex")
    .style("align-items", "center")
    .style("gap", "10px")
    .style("font-family", "Geist Mono, monospace")
    .style("font-size", "12px");

  let moments = selectMoments(data.events ?? [], maxMoments);
  let currentIndex = 0;
  let playing = false;
  let timerId = null;

  function goTo(index, { fireCallback = true } = {}) {
    currentIndex = Math.max(0, Math.min(moments.length - 1, index));
    if (fireCallback && onMoment && moments[currentIndex]) {
      onMoment(moments[currentIndex], currentIndex);
    }
    render();
  }

  function stopTimer() {
    if (timerId !== null) {
      clearTimeout(timerId);
      timerId = null;
    }
  }

  function advance() {
    if (currentIndex >= moments.length - 1) {
      playing = false;
      stopTimer();
      render();
      return;
    }
    timerId = setTimeout(() => {
      goTo(currentIndex + 1);
      if (playing) advance();
    }, stepDurationMs);
  }

  /** Begin playback from the start: reset, then advance through every moment. */
  function play() {
    if (!moments.length) return;
    playing = true;
    if (onReset) onReset();
    goTo(0);
    advance();
  }

  /** Stop playback without changing the current index. */
  function pause() {
    playing = false;
    stopTimer();
    render();
  }

  /**
   * Move the current index by delta, clamped to the moment list.
   *
   * @param {number} delta - e.g. 1 (next) or -1 (previous).
   */
  function step(delta) {
    pause();
    goTo(currentIndex + delta);
  }

  function render() {
    container.selectAll("*").remove();

    const controls = container.append("div").style("display", "flex").style("gap", "4px");
    controls.append("button")
      .attr("class", "reel-prev")
      .text("‹")
      .on("click", () => step(-1));
    controls.append("button")
      .attr("class", "reel-play")
      .text(playing ? "⏸" : "▶")
      .on("click", () => (playing ? pause() : play()));
    controls.append("button")
      .attr("class", "reel-next")
      .text("›")
      .on("click", () => step(1));

    const current = moments[currentIndex];
    container.append("div")
      .attr("class", "reel-moment")
      .style("flex", "1 1 auto")
      .text(current ? `${current.minute}' ${current.annotation}` : "No standout moments");

    const dots = container.append("div").attr("class", "reel-dots").style("display", "flex").style("gap", "5px");
    dots.selectAll(".reel-dot")
      .data(moments, (d) => d.eventId)
      .join("span")
      .attr("class", "reel-dot")
      .style("width", "6px")
      .style("height", "6px")
      .style("border-radius", "50%")
      .style("display", "inline-block")
      .style("cursor", "pointer")
      .style("background", (d, i) => (i === currentIndex ? "#9F1239" : "#E5E5E5"))
      .on("click", (event, d) => {
        pause();
        goTo(moments.indexOf(d));
      });
  }

  render();

  /**
   * Re-render with a new events array — re-selects moments, resets to index
   * 0, and stops any active playback.
   *
   * @param {Object} [next={}] - Partial update.
   * @param {Object} [next.data] - Replacement `{ events: [...] }` object.
   */
  function update(next = {}) {
    if (next.data !== undefined) {
      stopTimer();
      playing = false;
      moments = selectMoments(next.data.events ?? [], maxMoments);
      currentIndex = 0;
    }
    render();
  }

  return { container, update, play, pause, step };
}
