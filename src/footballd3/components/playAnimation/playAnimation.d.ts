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
 * @returns {{ g: d3.Selection, controls: { play: function():void, pause: function():void, seek: function(number):void }, update: Function }}
 *   g:        The outer <g class="ga"> group appended to pitch.g.
 *   controls: { play(), pause(), seek(clipSeconds) } — playback controls.
 *   update:   function({ frames?, playbackSpeed? }) — replace data or change speed.
 *             Speed changes restart the timer at the current position. Frame
 *             replacement resets to clip start.
 */
export function createPlayAnimation(pitch: any, data: any, config?: {
    playbackSpeed?: number;
    ballRadius?: number;
    ballColor?: string;
    ballStroke?: string;
    actorColor?: string;
    trailOpacity?: number;
    actorFadeOpacity?: number;
    onTimeUpdate?: Function;
}): {
    g: d3.Selection<any, any, any, any>;
    controls: {
        play: () => void;
        pause: () => void;
        seek: (arg0: number) => void;
    };
    update: Function;
};
import * as d3 from "d3";
