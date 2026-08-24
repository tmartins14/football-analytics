import * as d3 from "d3";

import { createPitch }         from "../../libs/footballd3/components/pitch/pitch.js";
import { createFormation }     from "../../libs/footballd3/components/formation/formation.js";
import { createPassNetwork }   from "../../libs/footballd3/components/passNetwork/passNetwork.js";
import { createTeamShape }     from "../../libs/footballd3/components/teamShape/teamShape.js";
import { createMatchStats }    from "../../libs/footballd3/components/matchStats/matchStats.js";
import { createMomentumChart } from "../../libs/footballd3/components/momentumChart/momentumChart.js";
import { createPlayAnimation } from "../../libs/footballd3/components/playAnimation/playAnimation.js";
import { createShotMap }       from "../../libs/footballd3/components/shotMap/shotMap.js";

const DATA = "/data/euro-2024/3943043";
const PITCH_PX = 4; // pxPerYard for team-column pitches

// ─── Load all data in parallel ─────────────────────────────────────────────

async function loadAll() {
  const [
    shots, spainPN, englandPN, matchStats,
    spainForm, englandForm, spainTS, englandTS,
    momentum, goalAnim, teamColors,
  ] = await Promise.all([
    fetch(`${DATA}/shots.json`).then(r => r.json()),
    fetch(`${DATA}/pass_network_Spain.json`).then(r => r.json()),
    fetch(`${DATA}/pass_network_England.json`).then(r => r.json()),
    fetch(`${DATA}/match_stats.json`).then(r => r.json()),
    fetch(`${DATA}/formation_spain.json`).then(r => r.json()),
    fetch(`${DATA}/formation_england.json`).then(r => r.json()),
    fetch(`${DATA}/team_shape_spain.json`).then(r => r.json()),
    fetch(`${DATA}/team_shape_england.json`).then(r => r.json()),
    fetch(`${DATA}/momentum.json`).then(r => r.json()),
    fetch(`${DATA}/goal_animation.json`).then(r => r.json()),
    fetch("/libs/footballd3/sample_data/team_colors.json").then(r => r.json()),
  ]);
  return { shots, spainPN, englandPN, matchStats, spainForm, englandForm, spainTS, englandTS, momentum, goalAnim, teamColors };
}

// ─── Toggle helpers ─────────────────────────────────────────────────────────

function activateToggle(groupEl, activeBtn) {
  groupEl.querySelectorAll(".toggle-btn").forEach(b => b.classList.remove("active"));
  activeBtn.classList.add("active");
}

function show(...els) { els.forEach(el => el && el.classList.remove("hidden")); }
function hide(...els) { els.forEach(el => el && el.classList.add("hidden")); }

// ─── TEAM COLUMN (Spain / England) ─────────────────────────────────────────

function mountTeamPanel(prefix, formData, pnData, tsData, teamShots, teamColor) {
  // ── Formation — createPitch treats its selection as the SVG, so provide one ──
  const formSvg = d3.select(`#${prefix}-formation`).append("svg");
  createFormation(formSvg, formData, { pxPerYard: PITCH_PX, nodeColor: teamColor });

  // ── Pass Network (caller provides pitch) ──
  const pnSvg   = d3.select(`#${prefix}-passnetwork`).append("svg");
  const pnPitch = createPitch(pnSvg, {
    theme: "whiteboard",
    pxPerYard: PITCH_PX,
    orientation: "vertical",
    flipAttack: true,    // forwards at top — matches formation view
  });
  // window: 0 = starting XI (first lineup window before any substitution)
  createPassNetwork(pnPitch, pnData, {
    window: 0,
    nodeColor: teamColor,
    edgeColor: teamColor,
  });

  const pnWindowSel = document.getElementById(`${prefix}-pn-window`);

  // ── Team Shape (caller provides pitch) ──
  const tsSvg   = d3.select(`#${prefix}-teamshape`).append("svg");
  const tsPitch = createPitch(tsSvg, {
    theme: "whiteboard",
    pxPerYard: PITCH_PX,
    orientation: "vertical",
    flipAttack: true,    // forwards at top — matches formation view
  });
  const teamShape = createTeamShape(tsPitch, tsData, { view: "on-ball", nodeColor: teamColor, accentColor: teamColor });

  const tsPeriodSel = document.getElementById(`${prefix}-ts-period`);
  tsData.on_ball.periods.forEach((p, i) => {
    const opt = document.createElement("option");
    opt.value = i;
    opt.textContent = `${p.from_minute}′–${p.to_minute}′`;
    tsPeriodSel.appendChild(opt);
  });
  tsPeriodSel.addEventListener("change", () => teamShape.updatePeriod(parseInt(tsPeriodSel.value)));

  // TeamShape sub-toggle
  const tsToggle = document.getElementById(`${prefix}-ts-toggle`);
  tsToggle.querySelectorAll(".toggle-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      activateToggle(tsToggle, btn);
      const view = btn.dataset.ts;
      teamShape.update(view);
      view === "on-ball" ? show(tsPeriodSel) : hide(tsPeriodSel);
    });
  });

  // ── Main panel toggle ──
  const mainToggle = document.getElementById(`${prefix}-toggle`);
  const containers = {
    formation:   document.getElementById(`${prefix}-formation`),
    passnetwork: document.getElementById(`${prefix}-passnetwork`),
    teamshape:   document.getElementById(`${prefix}-teamshape`),
  };
  const tsControls = document.getElementById(`${prefix}-ts-controls`);

  mainToggle.querySelectorAll(".toggle-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      activateToggle(mainToggle, btn);
      const view = btn.dataset.view;

      Object.entries(containers).forEach(([k, el]) =>
        k === view ? show(el) : hide(el)
      );

      // Pass-network window selector is hidden — dashboard shows starting XI only.
      hide(pnWindowSel);
      view === "teamshape" ? show(tsControls) : hide(tsControls);
    });
  });

  // ── Per-team shot map — always visible, below the pitch toggle ──
  // orientation:"vertical" produces a landscape 368×288 SVG (wider than tall)
  const smSvg = d3.select(`#${prefix}-shotmap`).append("svg");
  createShotMap(smSvg, teamShots, { theme: "whiteboard", pxPerYard: PITCH_PX, orientation: "vertical", color: teamColor });
}

// ─── CENTER COLUMN: Goal Animation | Match Stats | Momentum ─────────────────

function mountCenter(matchStats, momentum, goalAnim, homeColor, awayColor) {
  // ── Goal Animation view ──
  const animPitch = createPitch(
    d3.select("#animation-container").append("svg"),
    { theme: "whiteboard", pxPerYard: 5 }
  );

  let playing        = false;
  const scrubber     = document.getElementById("scrubber");
  const scrubberTime = document.getElementById("scrubber-time");

  const anim = createPlayAnimation(animPitch, goalAnim.goals[0], {
    playbackSpeed: 2.0,
    onTimeUpdate: (t) => {
      scrubber.value = t;
      scrubberTime.textContent = `${t.toFixed(1)}s`;
    },
  });

  scrubber.max   = goalAnim.goals[0].window.t_span_seconds;
  scrubber.value = 0;

  const goalSel = document.getElementById("goal-selector");
  goalAnim.goals.forEach((clip, i) => {
    const g   = clip.context?.goal;
    const lbl = g ? `Goal ${i + 1}: ${g.scorer} ${g.minute}'` : `Clip ${i + 1}`;
    const btn = document.createElement("button");
    btn.className = "toggle-btn" + (i === 0 ? " active" : "");
    btn.textContent = lbl;
    btn.addEventListener("click", () => {
      playing = false;
      document.getElementById("btn-play-pause").textContent = "▶ Play";
      anim.controls.pause();
      anim.update({ frames: clip.frames });
      anim.controls.seek(0);
      scrubber.max   = clip.window.t_span_seconds;
      scrubber.value = 0;
      scrubberTime.textContent = "0.0s";
      goalSel.querySelectorAll(".toggle-btn").forEach((b, j) =>
        b.classList.toggle("active", j === i)
      );
    });
    goalSel.appendChild(btn);
  });

  document.getElementById("btn-play-pause").addEventListener("click", (e) => {
    playing = !playing;
    e.currentTarget.textContent = playing ? "⏸ Pause" : "▶ Play";
    playing ? anim.controls.play() : anim.controls.pause();
  });

  scrubber.addEventListener("input", () => {
    anim.controls.seek(parseFloat(scrubber.value));
    scrubberTime.textContent = `${parseFloat(scrubber.value).toFixed(1)}s`;
  });

  // ── Match Stats view ──
  createMatchStats(d3.select("#center-stats-container"), matchStats, { width: 320 });

  // ── Momentum view ──
  // Flip home/away perspective so Spain (left column) reads on the left of the chart.
  // In vertical mode, positive momentum → right; Spain is home (positive) but sits in the
  // left dashboard column. Negating all values and swapping team labels corrects alignment.
  const flippedMomentum = {
    ...momentum,
    home_team: momentum.away_team,
    away_team: momentum.home_team,
    minutes: momentum.minutes.map(m => ({ ...m, momentum: -m.momentum })),
    secondary_minutes: (momentum.secondary_minutes ?? []).map(m => ({ ...m, momentum: -m.momentum })),
    goals: momentum.goals,
  };

  createMomentumChart(d3.select("#center-momentum-container"), flippedMomentum, {
    width: 440,
    height: 340,
    orientation: "vertical",
    homeColor: awayColor,  // "home" slot is now England (right column)
    awayColor: homeColor,  // "away" slot is now Spain (left column)
  });

  // ── 3-way center toggle ──
  const centerToggle = document.getElementById("center-toggle");
  const animView     = document.getElementById("animation-view");
  const statsEl      = document.getElementById("center-stats-container");
  const momentumEl   = document.getElementById("center-momentum-container");

  centerToggle.querySelectorAll(".toggle-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      activateToggle(centerToggle, btn);
      const view = btn.dataset.view;
      view === "animation" ? show(animView)   : hide(animView);
      view === "stats"     ? show(statsEl)    : hide(statsEl);
      view === "momentum"  ? show(momentumEl) : hide(momentumEl);
    });
  });
}

// ─── Init ───────────────────────────────────────────────────────────────────

async function init() {
  const data = await loadAll();

  // Team colors: single source of truth is team_colors.json
  const homeTeam   = data.matchStats.home.team;
  const awayTeam   = data.matchStats.away.team;
  const homeColor  = data.teamColors[homeTeam];
  const awayColor  = data.teamColors[awayTeam];

  // Override matchStats colors so stat bars use the canonical values from team_colors.json
  data.matchStats.home.color = homeColor;
  data.matchStats.away.color = awayColor;

  const spainColor   = homeTeam === "Spain"   ? homeColor : awayColor;
  const englandColor = awayTeam === "England" ? awayColor : homeColor;
  const spainShots   = data.shots.filter(s => s.team === homeTeam);
  const englandShots = data.shots.filter(s => s.team === awayTeam);

  mountTeamPanel("spain",   data.spainForm,   data.spainPN,   data.spainTS,   spainShots,   spainColor);
  mountTeamPanel("england", data.englandForm, data.englandPN, data.englandTS, englandShots, englandColor);
  mountCenter(data.matchStats, data.momentum, data.goalAnim, homeColor, awayColor);
}

init().catch(err => {
  console.error("Dashboard init failed:", err);
});
