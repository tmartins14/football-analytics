# Idea #2 — Defensive Decision Quality: Project Reference Document

## Status
**Tabled.** This document exists for future reference when foundations (idea #3, idea #1) are in place and tracking data access has been secured.

## Strategic framing

The Maldini intuition: *"If I have to make a tackle, I've already made a mistake."* Defensive value lives in pre-event positioning that constrains the opponent's strategy space, not in the tackle/interception/clearance events that traditional metrics count.

Existing event-based defensive metrics (tackles, interceptions, blocks, defensive VAEP) miss this entirely. The most valuable defensive actions are positional and continuous, not eventful and discrete. Tracking data is required to capture them.

## Prior art — what already exists

This project does not invent the field. It extends or reinterprets the following:

- **Le et al. (2017, MIT Sloan)** — *Data-Driven Ghosting using Deep Imitation Learning*. Trains a model on tracking data of good defenders, then evaluates any defender against the model's prediction of their optimal positioning. Methodological skeleton for any positioning-quality work.
- **Forcher et al. (2024)** — Bundesliga 2020/21 tracking data, 153 games. Predicts ball gains from defensive metrics (defensive pressure, distance to ball, inter-line distances, numerical superiority, surface area, spread). Closest existing thing to descriptive defensive analysis with tracking data.
- **Bauer et al. (2021, Springer)** — Counterpressing detection using XGBoost on six seasons of Bundesliga tracking data. AUC 87.4%. Quantifies offensive and defensive consequences per team.
- **Robberechts (2019, StatsBomb)** — *Valuing the Art of Pressing*. Direct attempt to assign value to pressing actions.
- **xDEF (Lamberts, January 2025)** — Expected Defensive Threat Reduction, combining event data with EPV and SkillCorner physical data. Ligue 1 season-level analysis.
- **Herold et al. (2022)** — Refined elliptical pressure model accounting for distance to goal.
- **Spearman et al. — OBSO** and Fernández/Bornn — pitch control and pitch value. Foundational spatial models that any defensive analysis builds on.

Read all of these before starting. The genuine contribution will only become clear after the prior art is fully understood.

## Possible angles of contribution

Three candidate research questions, ranked by feasibility-to-distinctiveness ratio:

### Candidate A — Counterfactual ghosting with causal interpretation

Extend Le et al. Train a model on tracking data of successful defensive sequences. At each frame, the model predicts where each defender should be. Score actual defenders by deviation from predicted optimal position, weighted by criticality of the moment.

The econometric twist: instead of treating the model's prediction as ground truth, treat it as a benchmark and use causal methods to identify *which deviations matter for outcomes*. Some deviations are mistakes, others are tactical variations that work. Distinguishing them requires causal inference, not just predictive modelling.

**Pros**: well-trodden methodology to build on, clear deliverable.
**Cons**: closest to existing work, hardest to claim originality.

### Candidate B — Pre-event positioning value (RECOMMENDED)

For each defensive sequence ending in either a chance conceded (high xGA) or successful defense, look at defender positions 3, 5, 10 seconds before the critical moment. Build a model predicting conditional probability of conceding xG given defensive shape at time t-k. Decompose into individual contributions.

The "decision" being valued is positioning before the event, not the event itself. Methodology requires a counterfactual: what would have happened with different positioning? Pitch control or EPV provides the proxy outcome.

**Pros**: closest to original Maldini intuition, most defensible novelty, substantial econometric content.
**Cons**: harder than Candidate A, requires credible counterfactual construction.

### Candidate C — Defensive option closure (most distinctive)

For each opposition possession, identify the passing/dribbling options available to the ball carrier. Measure how many dangerous options each defender closes (via positioning, body shape, distance). Defender value = dangerous options closed minus dangerous options left open.

Most game-theoretic framing. The defender chooses positions to minimize the maximum expected value the attacker can extract. Metric for a defender is how well they constrain the attacker's choice set.

**Pros**: most distinctive, strongest game-theory content, freshest framing.
**Cons**: requires the most novel methodology, least prior work to build on.

**Recommended path**: Candidate B for portfolio. Candidate C as an extension once B is working.

## Methodology — Candidate B detailed

### Step 1: Define the outcome
For each defensive sequence (opposition possession), compute the expected goals against (xGA) of the resulting opposition action. If no shot, xGA = 0. If shot, xGA = the xG value. Aggregate per possession.

### Step 2: Define the treatment
For each defender at each frame, compute features describing positioning relative to:
- The ball
- The attacker they are nominally responsible for
- The goal
- Their teammates' positions (defensive shape, line distances, lateral compactness)

These features at time t-k constitute the "treatment" for a possession that ends at time t. Choice of k (3s, 5s, 10s) matters and should be tested.

### Step 3: Estimate the conditional expected outcome
Model E[xGA | positioning at t-k, game state, opponent quality, score state]. Tree-based or neural net for flexibility, but with clear documentation of what is held constant.

Watch out for: tactical system as a confounder, opponent quality as a confounder, game state effects (leading vs trailing changes defensive behavior).

### Step 4: Decompose to player level
This is where the credit assignment problem bites.

- **Naive approach**: SHAP values per defender.
- **Better approach**: counterfactual swaps — replace one defender's position with the league-average defender at that role, recompute predicted xGA, attribute the difference. This is closer to the causal effect of *that defender's positioning choice*.

The "league-average defender at this role" needs to be properly constructed. Synthetic control across similar players is the right method.

### Step 5: Validate
- Out-of-sample prediction of conceded chances from positioning features.
- Year-on-year stability of player-level scores. Critical: defensive metrics notoriously have poor year-on-year stability. If yours does too, you cannot claim to capture a real player attribute.
- Face validity check with experienced tactical analysts.

### Output structure
Vector of metrics, **not** a single number:
- Closing-rate (how often does the defender close passing options to the ball carrier?)
- Lane-coverage (does the defender cover dangerous passing lanes?)
- Support-distance (does the defender maintain appropriate distance from teammates?)
- Recovery-positioning (after losing position, how quickly does the defender re-establish a useful one?)

Resist the temptation to summarise into a single composite score. The vector preserves information that makes the analysis useful to a coach. A composite hides where signal and noise live.

## Data requirements

### Minimum viable for prototype
- Metrica Sports public sample (3 matches, full tracking) — primary prototyping data.
- StatsBomb open data with 360 freeze frames (Euros, World Cup, Women's Super League) — extends to more games but lacks continuous tracking.
- Public event data (StatsBomb, FBref) for game state and opponent quality features.

### For serious work
- DFL Bundesliga Data Shootout — has released competitive tracking datasets in past years.
- Liverpool's analytics challenges — sample tracking data released for past competitions.
- SkillCorner academic partnership — has run partnerships with university researchers; explicit application required.
- Hudl/StatsBomb academic licenses if available.
- MIT Sloan Sports Analytics Conference data programs.

### Honest assessment
3 Metrica matches will not produce a publishable paper. They will produce a working methodology. The methodology is the asset; data scale follows.

## Where causal inference earns its keep

Step 4 (decomposition to player level) is the locus of identification. The counterfactual must be defensible:

- What is the comparison defender? "League-average at this role" requires careful role definition.
- What is held constant? Tactical system, opponent, game state, teammate quality must all be addressed.
- Is the assignment of player to position exogenous? Coaches choose lineups based on opponent — selection bias. Possible mitigations: injury-forced lineups, suspension-forced lineups, fixture congestion as quasi-exogenous variation.

The econometrics background is most valuable here. Without it, the decomposition is just SHAP values relabelled as "causal" — which is exactly the kind of overclaim the field is full of.

## Realistic timeline

| Phase | Duration | Deliverable |
|-------|----------|-------------|
| Literature review | ~1 month | Annotated reading of all prior art listed above |
| Prototype | ~2-3 months | End-to-end pipeline on 3 Metrica matches, methodology validated at small scale |
| Scaling | ~3-6 months | Apply to StatsBomb 360 data, refine methodology, secure academic data access |
| Validation and writeup | ~3-6 months | Year-on-year stability tests, face validity checks, paper or extended writeup |
| Publication / presentation | Variable | MIT Sloan, StatsBomb conference, Friends of Tracking, arXiv preprint |

Total: 12-18 months from start. The prototype on Metrica is the minimum viable deliverable. Do not let data-scale problems delay starting.

## Risks and failure modes

### Risk 1: Dominated by existing models
Counterpressing detection (Bauer), defensive ghosting (Le), pressure modeling (Herold) all overlap with parts of this. The defensible novelty is causal interpretation of the metrics. If the project ends up as "another descriptive defensive metric," it has failed strategically.

### Risk 2: Validation is hard
Defensive metrics have notoriously poor year-on-year stability. If the metric here also has poor stability, the claim that it captures a real player attribute fails. Plan the validation strategy upfront, not at the end.

### Risk 3: System-dependence
The "right defensive positioning" is tactical. Liverpool's right back is supposed to be high; Atlético's is supposed to be deep. A naive ghosting model pooling across teams will think one of them is mispositioned. Adjusting for tactical system requires care — possibly hierarchical models with team-level or coach-level random effects.

### Risk 4: Tracking data access becomes the bottleneck
Without continuous tracking, the project stalls at prototype. Backup plan: use StatsBomb 360 alone, accept the limitation that positioning is only observed at events, and frame the paper accordingly.

### Risk 5: Credit assignment is unsolvable in this design
Defensive value is collective. Decomposing it to individuals may always be partly arbitrary. If this turns out to be true, the honest move is to publish team-level or unit-level metrics rather than forcing individual numbers.

## What this project signals about Tyler

For positioning purposes, this project demonstrates:

- Ability to read academic literature and identify gaps rather than rebuilding well-trodden ground.
- Application of econometric identification to tracking data, which is rare in football analytics.
- Capacity to work with multiple data layers (event, freeze-frame, tracking).
- Understanding that defensive analysis is the field's weakest area, with a credible angle on it.

What it does **not** signal, and should not be pitched as:
- Production-grade pipeline engineering (the data engineering background is its own asset).
- A novel pitch control or EPV model (these exist; do not compete on this terrain).
- A single composite "defender rating" (resist this even if pressured to produce one).

## Prerequisites before tackling this seriously

1. Idea #3 (hierarchical estimation) completed — gives the partial-pooling toolkit needed for proper player-level inference here.
2. Idea #1 (causal identification) prototyped — establishes the identification-strategy muscle needed for step 4.
3. Tracking data access secured (Metrica at minimum, ideally an academic partnership).
4. Read at least Le et al., Forcher et al., Bauer et al., Robberechts, and the xDEF writeup in full. Confirm there isn't a recent paper that already does Candidate B.

## Open questions to resolve when picking this back up

- Is Candidate B still the right choice, or has the field moved? Re-survey prior art at restart.
- Has full tracking data become more accessible publicly? Check current state of DFL, SkillCorner academic programs, Hudl.
- Has anyone published a causal-inference-on-defensive-positioning paper in the interim? If so, read it before starting.
- Is the right deliverable a paper, a public dashboard, an open-source library, or all three? Decide based on portfolio strategy at restart.