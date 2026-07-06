/**
 * playAnimation.js — time-windowed ball-path animation over event data.
 *
 * Composes on pitch.js: receives an existing pitch object and draws the
 * animation into pitch.g using pitch.px() for coordinate conversion. Does not
 * create or re-render the pitch.
 *
 * WHAT THIS ANIMATES
 * The ball's path through the StatsBomb event sequence in the seconds surrounding
 * any anchor event: Pass → Carry → Shot sequences, with acting players highlighted
 * at their event origins. Point events (Pressure, Duel, Interception) cause the
 * ball to pause while the actor appears; ball paths are straight segments between
 * event start and end coordinates. Events from both teams are included.
 *
 * IMPORTANT LIMITATIONS
 * - This animates the BALL and players who touched it. StatsBomb open data has
 *   no continuous tracking; off-ball player movement and positioning are not shown.
 * - Ball paths are straight event-to-event line segments, not real trajectories.
 * - Players appear only at their events (where they touched the ball), not between.
 * - window_seconds is a configurable design choice; see README.md.
 *
 * PLAYBACK MODEL
 * The component owns its playback state (clipSeconds, playing/paused, d3.timer
 * handle) inside a closure. The timer fires every animation frame and updates
 * ball position by direct cx/cy attribute mutation (NOT d3.transition — transitions
 * cannot be interrupted mid-animation, which would break scrubbing). The scrubber
 * is wired externally via the onTimeUpdate callback; the component does not create
 * DOM controls.
 *
 * TRAIL ENCODING (mirrors progressiveMap.js — no arrowheads)
 *   Pass  → #9F1239 (red),  1.5px
 *   Carry → #1E3A5F (navy), 2.5px  (heavier line, matches progressive map)
 *   Shot  → #525252 (gray), 1.5px
 *
 * LAYER ORDER (inside pitch.g)
 *   ga-trails        — faded lines of completed ball segments, colored by type
 *   ga-actors        — previous actor halos at low opacity
 *   ga-actor-current — current actor ring + name label
 *   ga-ball          — ball circle (topmost)
 */

// ── Trail encoding (mirrors progressiveMap.js: Pass=red, Carry=navy) ─────────
//
// Differentiates ball-movement types by color and stroke weight on trail lines,
// matching the pass/carry map convention without arrowheads.
//   Pass  → #9F1239 (red),  1.5px
//   Carry → #1E3A5F (navy), 2.5px
//   Shot  → #525252 (gray), 1.5px
//   Other → #E5E5E5,        1.5px  (point events: no trail drawn)

function _frameColor(frame) {
  switch (frame.event_type) {
    case "Pass":  return "#9F1239";
    case "Carry": return "#1E3A5F";
    case "Shot":  return "#525252";
    default:      return "#E5E5E5";
  }
}

function _frameStrokeWidth(frame) {
  return frame.event_type === "Carry" ? 2.5 : 1.5;
}

// ── Segment builder ───────────────────────────────────────────────────────────

/**
 * Convert a normalized frame array into pixel-space animation segments.
 *
 * Each segment covers the ball's journey during one frame's time budget. For
 * movement events (ball_end_x present) the ball travels from origin to end. For
 * point events (ball_end_x null) the ball holds at origin for the segment's
 * duration. The final frame always receives LAST_FRAME_DURATION_SEC as its budget.
 *
 * @param {Array}    frames              - Normalized frames with a `clipTime` field.
 * @param {Function} px                  - pitch.px(sbX, sbY) → [pixelX, pixelY].
 * @param {number}   lastFrameDurationSec - Duration assigned to the final frame.
 * @returns {Array} Segment objects with pixel coords and timing.
 */
function _buildSegments(frames, px, lastFrameDurationSec = 1.0) {
  let accSec = 0;
  return frames.map((f, i) => {
    const next = frames[i + 1];
    const durationSec = next ? (next.t_seconds - f.t_seconds) : lastFrameDurationSec;
    const [fromPx, fromPy] = px(f.ball_x, f.ball_y);
    const isPoint = f.ball_end_x == null;
    const [toPx, toPy] = isPoint
      ? [fromPx, fromPy]
      : px(f.ball_end_x, f.ball_end_y);

    const seg = {
      frameIndex:  i,
      startSec:    accSec,
      durationSec: Math.max(durationSec, 0.05), // floor to avoid divide-by-zero
      fromPx, fromPy,
      toPx, toPy,
      isPoint,
    };
    accSec += seg.durationSec;
    return seg;
  });
}

// ── Position lookup ───────────────────────────────────────────────────────────

/**
 * Compute ball pixel position and active frame index at a clip-relative time.
 *
 * Iterates segments to find which one contains clipSec, then linearly
 * interpolates the ball position within that segment.
 *
 * @param {Array}  segments - Segment array from _buildSegments().
 * @param {number} clipSec  - Clip-relative time in seconds.
 * @returns {{ x: number, y: number, frameIndex: number }} Pixel coords + frame.
 */
function _posAtClipSec(segments, clipSec) {
  for (let i = 0; i < segments.length; i++) {
    const seg = segments[i];
    const segEnd = seg.startSec + seg.durationSec;
    if (clipSec <= segEnd || i === segments.length - 1) {
      const t = Math.max(0, Math.min(1, (clipSec - seg.startSec) / seg.durationSec));
      return {
        x:          seg.fromPx + t * (seg.toPx - seg.fromPx),
        y:          seg.fromPy + t * (seg.toPy - seg.fromPy),
        frameIndex: seg.frameIndex,
      };
    }
  }
  const last = segments[segments.length - 1];
  return { x: last.toPx, y: last.toPy, frameIndex: last.frameIndex };
}

// ── Main export ───────────────────────────────────────────────────────────────

/**
 * Animate the ball's path through a time-windowed event sequence.
 *
 * Appends four layered groups to pitch.g and drives a d3.timer-based animation
 * loop. Ball position is updated by direct attribute mutation inside the timer
 * callback so the scrubber can seek to any clip position without interrupting a
 * transition. The component does not create DOM controls; wire the scrubber via
 * the onTimeUpdate callback.
 *
 * Call createPitch() first and pass its return value as `pitch`.
 *
 * @param {Object} pitch - Return value of createPitch(). Must expose { g, px, svg }.
 * @param {Object} data  - One clip from the play animation contract. Must expose:
 *   data.frames: [{event_id, t_seconds, team, event_type, ball_x, ball_y,
 *                  ball_end_x, ball_end_y, actor, outcome}]
 *   data.window: {anchor_event_id, start_event_id, end_event_id, period,
 *                 window_seconds, t_span_seconds}
 *   data.context: {} — or {goal:{...}} when produced by extract_goal_animation
 * @param {Object}   [config={}]                   - Rendering options.
 * @param {number}   [config.playbackSpeed=2.0]    - Real-time multiplier. 2.0 means
 *   10s of real build-up plays back in 5s. Configurable; not canonical.
 * @param {number}   [config.ballRadius=5]         - Ball circle radius in pixels.
 * @param {string}   [config.ballColor="#FAF7F0"]  - Ball fill color.
 * @param {string}   [config.ballStroke="#171717"] - Ball stroke color.
 * @param {string}   [config.actorColor="#9F1239"] - Actor ring and highlight color.
 * @param {number}   [config.trailOpacity=0.15]    - Opacity of completed segment trails.
 * @param {number}   [config.actorFadeOpacity=0.12] - Opacity of previous actor halos.
 * @param {Function} [config.onTimeUpdate=null]    - Callback invoked on each animation
 *   tick and after seek: onTimeUpdate(clipSeconds). Use this to sync an external
 *   scrubber without the component touching the DOM directly.
 * @returns {{ g: d3.Selection, controls: Object, update: Function }}
 *   g:        The outer <g class="ga"> group appended to pitch.g.
 *   controls: { play(), pause(), seek(clipSeconds) } — playback controls.
 *   update:   function({ frames?, playbackSpeed? }) — replace data or change speed.
 *             Speed changes restart the timer at the current position. Frame
 *             replacement resets to clip start.
 */
export function createPlayAnimation(pitch, data, config = {}) {
  const {
    playbackSpeed:    initialSpeed    = 2.0,
    ballRadius                        = 5,
    ballColor                         = "#FAF7F0",
    ballStroke                        = "#171717",
    actorColor                        = "#9F1239",
    trailOpacity                      = 0.15,
    actorFadeOpacity                  = 0.12,
    onTimeUpdate                      = null,
  } = config;

  const { g, px } = pitch;

  // ── State ──────────────────────────────────────────────────────────────────

  let _frames        = data.frames;
  let _segments      = _buildSegments(_frames, px);
  let _clipDuration  = _segments.at(-1).startSec + _segments.at(-1).durationSec;
  let _clipSeconds   = 0.0;
  let _playing       = false;
  let _timer         = null;
  let _timerBase     = 0.0; // _clipSeconds value when the current timer was started
  let _playbackSpeed = initialSpeed;

  // ── DOM layers ─────────────────────────────────────────────────────────────

  const outerG        = g.append("g").attr("class", "ga");
  const trailsG       = outerG.append("g").attr("class", "ga-trails");
  const actorsG       = outerG.append("g").attr("class", "ga-actors");
  const actorCurrentG = outerG.append("g").attr("class", "ga-actor-current");
  const ballG         = outerG.append("g").attr("class", "ga-ball");

  // Ball circle — always present; position updated on every tick.
  const ballCircle = ballG.append("circle")
    .attr("r",            ballRadius)
    .attr("fill",         ballColor)
    .attr("stroke",       ballStroke)
    .attr("stroke-width", 1.5);

  // Initial render at clip start.
  _render(0);

  // ── Render ─────────────────────────────────────────────────────────────────

  /**
   * Stateless redraw of all layers at a given clip-relative time.
   *
   * Clears and rebuilds trails, actor halos, current actor ring, and ball position
   * from scratch. This makes seeking backward work correctly without accumulation.
   *
   * @param {number} clipSec - Clip-relative seconds to render.
   */
  function _render(clipSec) {
    const { x, y, frameIndex } = _posAtClipSec(_segments, clipSec);

    // Ball position.
    ballCircle.attr("cx", x).attr("cy", y);

    // Trails: completed segments (full length) + active segment (partial, to ball).
    trailsG.selectAll("*").remove();
    for (let i = 0; i < frameIndex; i++) {
      const s = _segments[i];
      if (!s.isPoint) {
        trailsG.append("line")
          .attr("x1", s.fromPx).attr("y1", s.fromPy)
          .attr("x2", s.toPx).attr("y2", s.toPy)
          .attr("stroke",         _frameColor(_frames[i]))
          .attr("stroke-width",   _frameStrokeWidth(_frames[i]))
          .attr("stroke-linecap", "round");
      }
    }
    // Active segment: grows from its start to the current ball position as the
    // ball moves, so the trail is drawn in real-time rather than appearing all
    // at once when the segment completes.
    const activeSeg = _segments[frameIndex];
    if (activeSeg && !activeSeg.isPoint) {
      trailsG.append("line")
        .attr("x1", activeSeg.fromPx).attr("y1", activeSeg.fromPy)
        .attr("x2", x).attr("y2", y)
        .attr("stroke",         _frameColor(_frames[frameIndex]))
        .attr("stroke-width",   _frameStrokeWidth(_frames[frameIndex]))
        .attr("stroke-linecap", "round");
    }

    // Previous actor halos: faded rings at each prior event origin.
    actorsG.selectAll("*").remove();
    for (let i = 0; i < frameIndex; i++) {
      const f = _frames[i];
      const [ax, ay] = px(f.ball_x, f.ball_y);
      actorsG.append("circle")
        .attr("cx",             ax)
        .attr("cy",             ay)
        .attr("r",              ballRadius + 4)
        .attr("fill",           "none")
        .attr("stroke",         actorColor)
        .attr("stroke-opacity", actorFadeOpacity)
        .attr("stroke-width",   1.5);
    }

    // Current actor: full-opacity ring + name label.
    actorCurrentG.selectAll("*").remove();
    if (frameIndex < _frames.length) {
      const cf = _frames[frameIndex];
      const [ax, ay] = px(cf.ball_x, cf.ball_y);

      // Dashed ring for point events (ball stationary); solid for movement events.
      actorCurrentG.append("circle")
        .attr("cx",               ax)
        .attr("cy",               ay)
        .attr("r",                ballRadius + 6)
        .attr("fill",             "none")
        .attr("stroke",           actorColor)
        .attr("stroke-width",     2)
        .attr("stroke-dasharray", cf.ball_end_x == null ? "4,3" : "none");

      actorCurrentG.append("text")
        .attr("x",                ax)
        .attr("y",                ay + ballRadius + 18)
        .attr("text-anchor",      "middle")
        .attr("font-family",      "Geist Mono, monospace")
        .attr("font-size",        "10px")
        .attr("fill",             "#525252")
        .attr("pointer-events",   "none")
        .text(cf.actor);
    }

    if (onTimeUpdate) onTimeUpdate(clipSec);
  }

  // ── Timer tick ────────────────────────────────────────────────────────────

  /**
   * Animation tick callback for d3.timer.
   *
   * Computes current clip time from the elapsed ms since timer start and the
   * playback speed multiplier. Returns true when the clip ends to stop the timer.
   *
   * @param {number} elapsed - Milliseconds since the timer was started.
   * @returns {boolean|undefined} true when playback reaches clip end.
   */
  function _tick(elapsed) {
    const clipSec = Math.min(
      _timerBase + (elapsed / 1000) * _playbackSpeed,
      _clipDuration,
    );
    _clipSeconds = clipSec;
    _render(clipSec);

    if (clipSec >= _clipDuration) {
      _timer.stop();
      _timer   = null;
      _playing = false;
      _renderGoalFlash();
      return true;
    }
  }

  // ── Goal flash ────────────────────────────────────────────────────────────

  /**
   * Brief expand-and-contract animation on the ball when playback reaches the
   * goal. A single one-shot d3.timer drives the radius interpolation.
   */
  function _renderGoalFlash() {
    const FLASH_MS = 600;
    const flashTimer = d3.timer((elapsed) => {
      const t = Math.min(elapsed / FLASH_MS, 1.0);
      // Sine envelope: expands then contracts back to original radius.
      ballCircle.attr("r", ballRadius * (1 + Math.sin(t * Math.PI) * 2.5));
      if (t >= 1.0) {
        ballCircle.attr("r", ballRadius);
        flashTimer.stop();
      }
    });
  }

  // ── Controls ──────────────────────────────────────────────────────────────

  /**
   * Start playback from the current clip position.
   *
   * If playback has reached the end, rewinds to 0 before starting. Does nothing
   * if already playing.
   */
  function play() {
    if (_playing) return;
    if (_clipSeconds >= _clipDuration) _clipSeconds = 0;
    _playing   = true;
    _timerBase = _clipSeconds;
    _timer     = d3.timer(_tick);
  }

  /**
   * Pause playback at the current clip position.
   *
   * Does nothing if already paused. The clip position is preserved so a
   * subsequent play() or seek() can continue from here.
   */
  function pause() {
    if (!_playing) return;
    _playing = false;
    if (_timer) {
      _timer.stop();
      _timer = null;
    }
  }

  /**
   * Jump to a specific clip-relative time and re-render.
   *
   * If playback was active, it continues from the new position. If paused,
   * the frame is re-rendered at the target position without starting playback.
   *
   * @param {number} clipSec - Target clip-relative seconds. Clamped to [0, clipDuration].
   */
  function seek(clipSec) {
    const wasPlaying = _playing;
    pause();
    _clipSeconds = Math.max(0, Math.min(clipSec, _clipDuration));
    _render(_clipSeconds);
    if (wasPlaying) play();
  }

  /**
   * Replace animation data or change playback speed.
   *
   * Changing playbackSpeed restarts the timer at the current position so the
   * new speed takes effect immediately without a position jump. Replacing frames
   * resets to clip start.
   *
   * @param {Object}  [opts={}]
   * @param {Array}   [opts.frames]         - Replace the frame array entirely.
   * @param {number}  [opts.playbackSpeed]  - New real-time multiplier.
   */
  function update(opts = {}) {
    if (opts.frames !== undefined) {
      const wasPlaying = _playing;
      pause();
      _frames       = opts.frames;
      _segments     = _buildSegments(_frames, px);
      _clipDuration = _segments.at(-1).startSec + _segments.at(-1).durationSec;
      _clipSeconds  = 0;
      _render(0);
      if (wasPlaying) play();
    }

    if (opts.playbackSpeed !== undefined) {
      const wasPlaying = _playing;
      pause();
      _playbackSpeed = opts.playbackSpeed;
      if (wasPlaying) play();
    }
  }

  return {
    g:        outerG,
    controls: { play, pause, seek },
    update,
  };
}
