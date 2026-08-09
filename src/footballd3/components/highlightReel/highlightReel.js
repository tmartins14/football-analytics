/**
 * highlightReel.js — compact play/step reel of one player's standout moments,
 * or, in "all" mode, every one of their events.
 *
 * A single row: play/step controls, a big minute readout, the current
 * moment's kind/description, and progress dots (one per moment, clickable —
 * suppressed in "all" mode, where a dot per event would be noise). Moment
 * selection is entirely client-side (no dedicated extractor) — see
 * selectMoments()/allEventsMoments() — and computed once per player, not
 * reactive to the current scrub position (the reel always considers the
 * whole match).
 *
 * TWO MODES, ONE DISPLAY
 * config.mode selects which list of moments is being played/stepped through,
 * but both render identically through the same play/pause/step/render code
 * below — this is what lets the combined Timeline card offer "play the
 * highlights or all events" without two separate playback UIs:
 *   - "highlights" (default) — selectMoments(): up to 5 curated standout
 *     moments (goals, best shot, top progressive actions).
 *   - "all" — allEventsMoments(): every one of the player's events, in
 *     chronological order, each with its own kind/note text.
 *
 * THIS COMPONENT DOES NOT OWN THE SCRUBBER
 * Per the app's state model, `scrubbedMinute` has exactly one writer: the
 * master scrubber (scrubber.js). highlightReel.js never calls a scrubber
 * directly — it only reports "move to this minute" via onScrubTo(minute).
 * The consuming panel is responsible for calling the scrubber's own
 * seek()/onScrub() in response, exactly as it would for a direct drag. This
 * keeps the single-writer invariant intact even though playback is driven
 * from a second component.
 *
 * PLAY VS STEP
 * Play jumps straight to the first moment's minute, then advances through
 * the rest on a config.stepDurationMs interval, stopping (not looping) once
 * the last moment is reached. The step buttons (prev/next) stop any running
 * playback and move the current index by one immediately.
 */

const DEFAULT_STEP_MS = 1800;

/**
 * Auto-select up to 5 standout moments from a player's full-match events:
 * every goal, then the single highest-xG non-goal shot, then the top 3
 * positive-xt_delta Pass/Carry actions — combined and sorted chronologically,
 * then truncated to 5. This is a plain chronological truncation with no
 * goal-priority protection: with more than 5 combined candidates, the
 * latest-occurring ones are dropped even if one is a goal.
 *
 * @param {Array<Object>} events - Full player_events array (not scrub-filtered).
 * @returns {Array<{ minute: number, location: [number, number],
 *   end_location: [number, number]|null, kind: string, note: string,
 *   event_id: string }>} Chronologically ordered moments, at most 5.
 */
export function selectMoments(events) {
  const moments = [];

  events
    .filter((e) => e.is_goal)
    .forEach((e) => moments.push(_moment(e, "Goal", `Goal · xG ${(e.shot_xg ?? 0).toFixed(2)}`)));

  events
    .filter((e) => e.type === "Shot" && !e.is_goal)
    .sort((a, b) => (b.shot_xg ?? 0) - (a.shot_xg ?? 0))
    .slice(0, 1)
    .forEach((e) => moments.push(_moment(e, "Shot", `Shot · xG ${(e.shot_xg ?? 0).toFixed(2)} · ${e.outcome ?? "—"}`)));

  events
    .filter((e) => (e.type === "Pass" || e.type === "Carry") && (e.xt_delta ?? 0) > 0)
    .sort((a, b) => b.xt_delta - a.xt_delta)
    .slice(0, 3)
    .forEach((e) => {
      const typeLower = e.type.toLowerCase();
      const kind = e.is_progressive ? `Prog. ${typeLower}` : e.type;
      const note = `${e.is_progressive ? "Progressive " : ""}${typeLower} · +${e.xt_delta.toFixed(3)} xT`;
      moments.push(_moment(e, kind, note));
    });

  moments.sort((a, b) => a.minute - b.minute);
  return moments.slice(0, 5);
}

/**
 * Build one moment record from a source event.
 *
 * @param {Object} event - One player_events event.
 * @param {string} kind  - Short category label (e.g. "Goal", "Prog. pass").
 * @param {string} note  - Full description line.
 * @returns {Object} { minute, location, end_location, kind, note, event_id }
 */
function _moment(event, kind, note) {
  return {
    minute: event.minute,
    location: event.location,
    end_location: event.end_location ?? null,
    kind,
    note,
    event_id: event.event_id,
  };
}

/**
 * Build every event's own moment record, in chronological order — the "all
 * events" mode's moment list, one step per event rather than a curated
 * top-5. Reuses selectMoments()'s exact copy for Goal/Shot/Pass/Carry so the
 * two modes read consistently, and adds a generic fallback (`"{type}"`, or
 * `"{type} · {outcome}"` when there's an outcome) for every other event type
 * (Pressure, Duel, Ball Recovery, etc.), which selectMoments() never needs to
 * describe since it only ever selects goals/shots/positive-xT passes-carries.
 *
 * @param {Array<Object>} events - Full player_events array (not scrub-filtered).
 * @returns {Array<Object>} Every event as a moment record (see _moment),
 *   sorted chronologically by minute.
 */
export function allEventsMoments(events) {
  return events
    .map((e) => {
      if (e.is_goal) {
        return _moment(e, "Goal", `Goal · xG ${(e.shot_xg ?? 0).toFixed(2)}`);
      }
      if (e.type === "Shot") {
        return _moment(e, "Shot", `Shot · xG ${(e.shot_xg ?? 0).toFixed(2)} · ${e.outcome ?? "—"}`);
      }
      if (e.type === "Pass" || e.type === "Carry") {
        const typeLower = e.type.toLowerCase();
        const kind = e.is_progressive ? `Prog. ${typeLower}` : e.type;
        const v = e.xt_delta ?? 0;
        const note = `${e.is_progressive ? "Progressive " : ""}${typeLower} · ${v >= 0 ? "+" : ""}${v.toFixed(3)} xT`;
        return _moment(e, kind, note);
      }
      return _moment(e, e.type, e.outcome ? `${e.type} · ${e.outcome}` : e.type);
    })
    .sort((a, b) => a.minute - b.minute);
}

/**
 * Style one transport button (prev/play/next) — bordered, rounded, monospace.
 *
 * @param {d3.Selection} button - The <button> selection to style.
 * @param {Object} colors - Color tokens.
 * @param {string} colors.borderColor - Button border color.
 * @param {string} colors.buttonBackground - Button fill color.
 * @param {string} colors.textColor - Button label color.
 */
function _styleTransportButton(button, { borderColor, buttonBackground, textColor }) {
  button
    .style("min-width", "38px")
    .style("padding", "7px 12px")
    .style("border-radius", "6px")
    .style("border", `1px solid ${borderColor}`)
    .style("background", buttonBackground)
    .style("color", textColor)
    .style("font-family", "Geist Mono, monospace")
    .style("font-size", "14px")
    .style("cursor", "pointer");
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
 * @param {string}   [config.mode="highlights"] - "highlights" (up to 5
 *   curated moments via selectMoments()) or "all" (every event via
 *   allEventsMoments(), chronological, no progress dots).
 * @param {number}   [config.stepDurationMs=1800] - Milliseconds between
 *   moments during Play.
 * @param {string}   [config.teamColor] - Accepted for API-shape parity with
 *   the design spec, but intentionally unused — the reference implementation
 *   this component is built against never reads it either; every reel color
 *   comes from the focal/text/faint/border tokens below.
 * @param {Function|null} [config.onScrubTo=null] - onScrubTo(minute) fires
 *   on every step (Play advancing, or a manual prev/next/dot click/click).
 * @param {Function|null} [config.onHoverEvent=null] - onHoverEvent(eventId | null)
 *   fires on hover/unhover of the current moment's description.
 * @param {string} [config.borderColor="#E5E5E5"] - Transport button border.
 * @param {string} [config.buttonBackground="#FFFFFF"] - Prev/next button fill.
 * @param {string} [config.textColor="#171717"] - Body text color.
 * @param {string} [config.faintColor="#8A8578"] - Label/empty-state text color.
 * @param {string} [config.focalColor="#9F1239"] - Accent color (minute, Play
 *   button fill, active dot).
 * @param {string} [config.focalTextColor="#FAF7F0"] - Text color on the
 *   (always-filled) Play button — the theme's own background color.
 * @param {string} [config.inactiveDotColor="#D6D3CC"] - Inactive progress dot fill.
 * @returns {{ container: d3.Selection, update: Function, play: Function,
 *   pause: Function, step: Function }}
 *   container — the reel's root D3 selection.
 *   update({ data?, mode?, stepDurationMs? }) — re-render, optionally with a
 *     new events array and/or mode (re-selects moments, resets to index 0,
 *     stops any active playback) and/or a new step cadence.
 *   play() — begin playback from the start.
 *   pause() — stop playback without changing the current index.
 *   step(delta) — move the current index by delta (e.g. 1 or -1), clamped to
 *     the moment list, firing onScrubTo immediately.
 */
export function createHighlightReel(selection, data, config = {}) {
  let {
    mode             = "highlights",
    stepDurationMs   = DEFAULT_STEP_MS,
    onScrubTo        = null,
    onHoverEvent     = null,
    borderColor      = "#E5E5E5",
    buttonBackground = "#FFFFFF",
    textColor        = "#171717",
    faintColor       = "#8A8578",
    focalColor       = "#9F1239",
    focalTextColor   = "#FAF7F0",
    inactiveDotColor = "#D6D3CC",
  } = config;

  const container = selection.append("div")
    .attr("class", "highlight-reel")
    .style("display", "flex")
    .style("align-items", "center")
    .style("gap", "14px")
    .style("flex-wrap", "wrap");

  let currentData = data;
  let moments = mode === "all" ? allEventsMoments(currentData.events ?? []) : selectMoments(currentData.events ?? []);
  let currentIndex = 0;
  let playing = false;
  let timerId = null;

  function stopTimer() {
    if (timerId !== null) {
      clearInterval(timerId);
      timerId = null;
    }
  }

  /** Begin playback: jump to the first moment, then advance every stepDurationMs. */
  function play() {
    if (playing) {
      pause();
      return;
    }
    if (!moments.length) return;
    playing = true;
    currentIndex = 0;
    if (onScrubTo) onScrubTo(moments[0].minute);
    render();
    timerId = setInterval(() => {
      const next = currentIndex + 1;
      if (next >= moments.length) {
        stopTimer();
        playing = false;
        render();
        return;
      }
      currentIndex = next;
      if (onScrubTo) onScrubTo(moments[currentIndex].minute);
      render();
    }, stepDurationMs);
  }

  /** Stop playback without changing the current index. */
  function pause() {
    stopTimer();
    playing = false;
    render();
  }

  /**
   * Stop any playback and move to a specific moment index, firing onScrubTo.
   *
   * @param {number} index - Target index, clamped to [0, moments.length - 1].
   */
  function seekIndex(index) {
    pause();
    if (!moments.length) return;
    currentIndex = Math.max(0, Math.min(moments.length - 1, index));
    if (onScrubTo) onScrubTo(moments[currentIndex].minute);
    render();
  }

  /**
   * Stop any playback and move the current index by delta, firing onScrubTo.
   *
   * @param {number} delta - e.g. 1 (next) or -1 (previous).
   */
  function step(delta) {
    seekIndex(currentIndex + delta);
  }

  function render() {
    container.selectAll("*").remove();

    if (!moments.length) {
      container.append("div")
        .attr("class", "reel-empty")
        .style("font-family", "Geist Mono, monospace")
        .style("font-size", "11px")
        .style("color", faintColor)
        .text("No standout moments in the revealed window.");
      return;
    }

    const controls = container.append("div").style("display", "flex").style("gap", "6px");

    _styleTransportButton(
      controls.append("button").attr("class", "reel-prev").text("‹").on("click", () => step(-1)),
      { borderColor, buttonBackground, textColor }
    );

    const playButton = controls.append("button")
      .attr("class", "reel-play")
      .text(playing ? "❚❚ Stop" : "▶ Play")
      .on("click", () => (playing ? pause() : play()));
    _styleTransportButton(playButton, { borderColor, buttonBackground, textColor });
    playButton
      .style("background", focalColor)
      .style("border", `1px solid ${focalColor}`)
      .style("color", focalTextColor)
      .style("min-width", "78px");

    _styleTransportButton(
      controls.append("button").attr("class", "reel-next").text("›").on("click", () => step(1)),
      { borderColor, buttonBackground, textColor }
    );

    const current = moments[currentIndex];

    container.append("div")
      .attr("class", "reel-minute")
      .style("font-family", "Fraunces, serif")
      .style("font-weight", "900")
      .style("font-size", "28px")
      .style("color", focalColor)
      .style("min-width", "50px")
      .text(`${current.minute}'`);

    const desc = container.append("div")
      .attr("class", "reel-moment")
      .style("flex", "1 1 auto")
      .style("min-width", "180px")
      .style("cursor", "default")
      .on("mouseenter", () => onHoverEvent && onHoverEvent(current.event_id))
      .on("mouseleave", () => onHoverEvent && onHoverEvent(null));

    desc.append("div")
      .attr("class", "reel-moment-label")
      .style("font-family", "Geist Mono, monospace")
      .style("font-size", "11px")
      .style("letter-spacing", "0.08em")
      .style("text-transform", "uppercase")
      .style("color", faintColor)
      .style("margin-bottom", "3px")
      .text(`Moment ${currentIndex + 1} / ${moments.length} · ${current.kind}`);

    desc.append("div")
      .attr("class", "reel-moment-note")
      .style("font-family", "Geist, sans-serif")
      .style("font-size", "14px")
      .style("color", textColor)
      .text(current.note);

    // Suppressed in "all" mode — a dot per event (often 100+) is noise, and
    // the "Moment i / n" label line above already conveys position.
    if (mode !== "all") {
      const dots = container.append("div").attr("class", "reel-dots").style("display", "flex").style("gap", "6px");
      dots.selectAll(".reel-dot")
        .data(moments, (d) => d.event_id)
        .join("span")
        .attr("class", "reel-dot")
        .style("width", (d, i) => (i === currentIndex ? "20px" : "8px"))
        .style("height", "8px")
        .style("border-radius", "999px")
        .style("display", "inline-block")
        .style("cursor", "pointer")
        .style("transition", "width 0.2s")
        .style("background", (d, i) => (i === currentIndex ? focalColor : inactiveDotColor))
        .on("click", (event, d) => seekIndex(moments.indexOf(d)));
    }
  }

  render();

  /**
   * Re-render, optionally with a new events array and/or mode — either one
   * re-selects moments, resets to index 0, and stops any active playback.
   *
   * @param {Object} [next={}] - Partial update.
   * @param {Object} [next.data] - Replacement `{ events: [...] }` object.
   * @param {string} [next.mode] - "highlights" | "all".
   * @param {number} [next.stepDurationMs] - New cadence for future Play calls.
   */
  function update(next = {}) {
    if (next.stepDurationMs !== undefined) stepDurationMs = next.stepDurationMs;
    if (next.data !== undefined || next.mode !== undefined) {
      stopTimer();
      playing = false;
      if (next.data !== undefined) currentData = next.data;
      if (next.mode !== undefined) mode = next.mode;
      moments = mode === "all" ? allEventsMoments(currentData.events ?? []) : selectMoments(currentData.events ?? []);
      currentIndex = 0;
    }
    render();
  }

  return { container, update, play, pause, step };
}
