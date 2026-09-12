# SPEC: <match-analysis-dashboard-responsiveness-fix>

<!--
HOW TO FILL THIS IN — the interview pattern.

Paste this into a chat and say:

  "Interview me to fill in this spec. Ask one question at a time. Don't write
   any code. Don't fill in a section until I've answered for it. Push back if
   an answer is vague or if the scope is too big for one session."

Answer the questions, let it write the spec, read it, fix it yourself.
Then START A FRESH SESSION and hand it the finished spec. The interview
context is what makes the spec good and what makes execution bad — leave
it behind.
-->

## Goal
<!-- One line. If it needs two, it's two tasks. -->
The match analysis dashboard should work on all screens.

## Context
<!-- What exists today. Why this is being changed now. -->
There is a tylermartins.com/app/football/dashboard/page.tsx that does work on a computer screen but not on smaller screens.


## Files and interfaces involved
<!-- Actual paths. Function/class names it will touch or create.
     If you don't know them yet, that's a Plan-mode session, not this. -->
The 5 pitch panels are the real blocker. FormationPanel, PassNetworkPanel, TeamShapePanel, ShotMapPanel, GoalsBuildupPanel all hardcode pxPerYard. The fix is to measure container width (via a small shared useContainerWidth hook using ResizeObserver, not just clientWidth-on-mount) and derive pxPerYard from it, rather than editing the shared footballd3/pitch.js — confirmed that file is a workspace package also consumed directly by the legacy football-analytics/pages/match-analysis/dashboard.js, so touching it is riskier than solving this entirely inside the Next.js app's own panel components.


## Approach
<!-- The shape of the change, not the code. Decisions already made,
     so it doesn't re-litigate them mid-session. -->
Height-clip fix for TeamColumnCard/CenterColumnCard: since upperHeight is a JS prop (not a static value), the plan uses a CSS custom property (--upper-h) plus a Tailwind lg:h-[var(--upper-h)] arbitrary-value class, so the fixed-height clip only applies at lg:+ and content auto-sizes below that — while still following the constraint to prefer Tailwind responsive prefixes over inline-style-based JS branching.


## Out of scope
<!-- The most valuable section. Name the adjacent things it must NOT touch:
     refactors, renames, "while I'm in here" cleanups, unrelated tests. -->
Do not touch the component gallery.

## Verification
<!-- The pass/fail signal. Must be a command that exits 0 or non-zero,
     runnable without you. "Looks right" is not verification.

     Command:
     Expected:
     If this fails, stop and report — do not attempt a workaround. -->
There is currently no verification step in place. Create one.
