# Data-Driven Ghosting using Deep Imitation Learning (Le, Carr, Yue, Lucey 2017)

**Source:** [MIT Sloan Sports Analytics Conference 2017 PDF](https://s3-us-west-1.amazonaws.com/disneyresearch/wp-content/uploads/20170228130457/Data-Driven-Ghosting-using-Deep-Imitation-Learning-Paper1.pdf). Caltech / Disney Research / STATS LLC.

**Conceptual lineage:** Builds on the Toronto Raptors' 2013 "ghosting" concept (described in Zach Lowe's Grantland article), which required substantial manual annotation. Le et al.'s contribution is automation via deep imitation learning.

## What the paper does

Predicts counterfactual defensive positioning at frame-level resolution using deep imitation learning trained on tracking data. Compares actual defensive movements to a learned "league-average" model and to team-specific models (e.g., Manchester City). Conceptually distinct from every other paper this week — produces *prescriptive* (or "predicted alternative") output rather than *descriptive* metrics.

## Framework on the five design axes

| Axis | Ghosting |
|---|---|
| **State** | 22 player positions + ball + velocities; role-aligned via Hungarian algorithm to learn 4-4-2-shaped Gaussian role centroids; 399-dim feature vector per role per frame (absolute coordinates + relative polar coordinates to ball, goal, modelled role; closest-3 mini-blocks duplicated) |
| **Target** | Player position at next time step (10 fps). Predicting trajectory, not value. |
| **Horizon** | Frame-by-frame, rolled forward over 10-second sequences (~100 frames) |
| **Architecture** | LSTM per defensive role (2 hidden layers × 512 units). Trained via deep imitation learning (DAGGER-style two-phase algorithm: single-agent then multi-agent joint training) to handle compounding sequential error. Team-style adaptation via team-identity vector (analogous to style transfer). |
| **Credit assignment** | None at player level by design. Credit lives in the *deviation* between actual and ghost. Player-level value is downstream of pairing Ghosting with a value model. |

The State and Architecture axes are dramatically different from everything else this week. Target is the most interesting shift: other models predict *value*; this predicts *behaviour*. The combination is modular — Ghosting slots into existing value pipelines rather than competing with them.

## Key methodological points

- **Imitation learning is conservative by design.** Learns the *observed expert* policy. League-average ghost = league-average behaviour; team-style ghost = that team's behaviour. The model has no concept of *optimal* play — only what teams have done. Cannot generate novel optimal strategies. If the entire league has a systematic blind spot, the ghost reproduces it. The paper's "should have" framing conflates "what teams do on average" with "what is optimal" — these are different.

- **Compounding error is non-trivial.** Naive sequence prediction error grows to 20-30m over a 100-frame sequence. The DAGGER-style imitation learning approach drops average deviation to ~4m. This is the *technical* contribution that makes the system viable.

- **Role alignment loses player-specific information.** Each role gets one model; team-style is the only deviation channel. Individual player attributes (pace, technical ability, decision tendencies) are absorbed into noise within a role.

- **Modular by design.** Outputs trajectories. EGV / pitch control / pitch value are applied *on top of* the ghost trajectories. Ghosting alone produces no player-evaluation metric.

- **No causal identification.** Most important methodological gap. The simulation holds attack fixed and varies defence. Four concrete mechanisms by which the counterfactual breaks:

  1. **Attack-defence dependency.** Attacks respond to defensive shape; holding attack fixed assumes the same play would have unfolded against a different defence.
  2. **Game-state path dependence.** Initial positions inherited from actual play already reflect prior defensive decisions; the ghost is initialised in a state the ghost-team would never have reached.
  3. **Player capability vs role policy.** The MCG ghost prescribes ManCity's policy in Swansea's left back's body — different speed/acceleration/skill execution capability.
  4. **Within-sequence response.** Even within 10 seconds, attack and defence co-adapt; the simulation only propagates the attack forward, not the defensive response back into attack decisions.

  Imitation learning on observational data cannot resolve these. Causal identification requires either experimental variation (impossible), natural experiments (rare), or structural counterfactual modelling with explicit assumptions (the econometric path).

## Empirical claims

- **Average deviation ~4m** across all players/teams between actual and league-average ghost. Deviation increases for attacking-oriented positions (more variation in how forwards defend).
- **Out-of-position 80-20 rule:** teams with both top and bottom defensive performance (goals conceded) are outliers on positional deviation. Defensive *consistency* doesn't directly predict performance.
- **61.8% correlation** between team-style ghost EGV (across all 6020 open-play shot events) and actual goals conceded. The strongest empirical claim — a pure behavioural model trained from tracking alone has signal about season-long defensive outcomes.
- **Case study (Swansea vs Fulham):** actual EGV ~70%, LAG EGV ~70%, MCG EGV ~40%. Two specific players' positioning decisions drive the gap. Selected example; not systematic.

## What this paper actually contributes (ranked)

1. **The Ghosting paradigm itself.** Counterfactual behavioural prediction rather than valuing observed behaviour. Modular. Conceptually distinct from anything else this week.
2. **Imitation learning at scale for football tracking.** First demonstration of automatic policy learning from tracking data alone, without manual annotation.
3. **Team-style adaptation via domain adaptation.** Lets you ask "how would Team X defend this?" with quantitative output. The 0.62 correlation with actual defensive performance is real signal.
4. **The fine-grained case-study mode.** Player-level decision-level analysis at the frame resolution. Closer to coaching analysis than aggregate metrics produce.

## What to be sceptical of

1. **"Should have" rhetoric outruns methodology.** The model predicts what teams *do*, not what they *should do*. Different objects; the paper conflates them.
2. **League-average has two distortions.** (a) Averaging across teams with incompatible defensive philosophies produces an intermediate policy no team actually plays — the "mean of bimodal distributions" problem. (b) Observed defensive policies are conditional on attacker behaviour that was itself selecting for those defences — endogeneity, no instrument.
3. **Cover shadow and offside aren't captured.** Pitch-control-level limitations carry over; Ghosting models positions but doesn't surface non-local defensive contributions. Cover shadow is likely below the spatial resolution of the model given 100 games of training data.
4. **Sample size for team-style.** 100 games / 20 teams = ~5 games per team-style. Style transfer with that volume is noisy.
5. **EGV is the authors' own prior work.** Validation uses Lucey et al. 2015. If the EGV model has systematic biases, the validation inherits them.

## Pairing with OBSO — and what's already been done

The natural complementary pairing is Ghosting × OBSO. Ghosting generates counterfactual defender trajectories; OBSO decomposes attacking scoring opportunity by attacker conditional on configuration. The combination produces *prescriptive, attacker-decomposed, outcome-grounded* analysis rather than the paper's *prescriptive, team-aggregated EGV* analysis. It allows asking "under counterfactual defensive policy, which specific attacker would have had elevated scoring opportunity, and what would each defender have needed to do to neutralise them."

The combination exists in the literature:
- **Teranishi & Fujii (2021)**, "Making Offensive Play Predictable" — explicitly proposes evaluating team defensive positioning by computing counterfactuals via OBSO-style reasoning, searches for optimal defensive positioning over counterfactuals.
- **Tüting et al. 2026 (arXiv 2601.00748)** — introduces "role-conditioned ghosts" addressing tactical-context gaps in standard ghosting, combining with possession-value models for defensive evaluation.

What is *not* done in this lineage is the combination with proper causal identification. Existing work still uses observational data with imitation-learning conservatism — same strategic-interaction problem as the original paper, just with better tactical context. The genuinely open research direction is the causal-identification machinery on top of the combination.

The alternative pairings (Ghosting × WOS, Ghosting × Brefeld, Ghosting × SkillCorner) are weaker. WOS and Brefeld inherit defender-revealed pitch value, which doesn't address the circularity problem; swapping in ghost trajectories doesn't change the training signal of the value model. SkillCorner's opportunity-adjustment framework on a counterfactual defence is interesting but produces an opportunity-side measurement rather than an outcome-grounded evaluation.

## Connections going forward

- **Teranishi & Fujii 2021** and **Tüting et al. 2026 (arXiv 2601.00748)** — the natural follow-on reading for the Ghosting × OBSO combination. Both extend the Ghosting paradigm with tactical context.
- **Pearl's *Book of Why*** — conceptual scaffolding for what proper causal identification would require beyond what these papers do. Structural counterfactual models with explicit identification assumptions.
- The Ghosting paradigm is the closest existing work in this canon to causal counterfactual reasoning; understanding its causal-identification gap is the prerequisite for contributing original work on prescriptive defensive evaluation.

## Logged for OPEN_QUESTIONS.md

1. **Causally-identified counterfactual defensive evaluation.** Combine Ghosting (or its successors with tactical context) with explicit causal identification machinery — structural counterfactual modelling, instrumental variation, or natural experiments. The combination itself exists; the causal identification does not. Phase 3 research direction, not portfolio question.

2. **Modelling the strategic-interaction problem in counterfactual football simulation.** Specifically: jointly modelling attacker response to counterfactual defensive policy. Inverse reinforcement learning is one approach; structural game-theoretic equilibrium another. Less data-hungry than full causal identification; more tractable as intermediate work.

3. **Empirical bounds on the counterfactual recursion.** Even without solving causal identification, the *magnitude* of the error introduced by holding attack fixed could be estimated via held-out sequences where the same attacking team faced different defensive shapes. Tractable as portfolio question.

**Do not log:** "Combine Ghosting and OBSO." Already done. Reinventing existing work.

## On the first-to-arrive assumption (cumulative Week 2 note)

A recurring critique across the spatial-models lineage is that pitch control assumes a player's "control" of a point on the pitch is determined by who reaches it first. This produces misleading conclusions about defensive contributions whose value is non-local — cover shadow (defender on the passing line, not at the receiver's location), offside step-up (defender moves *away* from the attacker to nullify them via the line), recovery runs, positioning to deter rather than to challenge.

Ghosting bypasses pitch control entirely — it models positions directly without computing a control surface — which means it *avoids* the first-to-arrive problem but doesn't *solve* it. Anything downstream that runs pitch control on ghost trajectories inherits the first-to-arrive limitation. Across Week 2's spatial models, no paper solves this. The closest gestures are Ghosting (which sidesteps it) and SkillCorner's progressive passing (which models trajectories, where reachability could in principle be modelled along the trajectory). Neither does the work.