# Wide Open Spaces (Fernández & Bornn, 2018)

**Source:** MIT Sloan Sports Analytics Conference 2018. [PDF](https://www.lukebornn.com/papers/fernandez_ssac_2018.pdf)

## What the paper does

First serious attempt to operationalise off-ball value at scale using tracking data. Builds two metrics — **Space Occupation Gain (SOG)** and **Space Generation Gain (SGG)** — from a stack of three components: a parametric pitch control model, a learned pitch value model, and a quality-of-owned-space construct.

Demonstration: one La Liga match (Barcelona vs Villareal, Jan 2017). Validation: two FCB analysts watching clips. No predictive holdout, no outcome grounding.

## Framework on the five design axes

| Axis | Wide Open Spaces |
|---|---|
| **State** | 22-player + ball spatial configuration; positions and velocities; continuous-time tracking |
| **Target** | Quality of owned space $Q_i(t) = PC_i(t) \cdot V(t)$ |
| **Horizon** | Instantaneous for $Q$; 3-second window for SOG/SGG |
| **Architecture** | Decomposed: parametric Gaussian pitch control + learned (FFNN) pitch value, multiplied; rule-based SGG on top |
| **Credit assignment** | SOG = self-credit; SGG = relational credit (geometric rule for dragging defenders) |

The shift from event-data models (VAEP, xT, EPV) is on the **State** axis — discrete ball-touch sequence becomes continuous spatial field. That changes what targets are definable and what credit-assignment problems become tractable vs newly broken.

## Component breakdown

**Pitch Control ($PC$).** Each player's influence at point $p$ is a bivariate Gaussian shaped by position, velocity, and distance to ball. Team-level control = logistic of the difference between team influence sums. Analytical, no training. Single isolated player controls $\sigma(1) \approx 0.73$ of own location → density required for high control.

**Pitch Value ($V$).** Learned from defender position as revealed-preference proxy for danger: averaged over many situations, defenders cluster on valuable spaces given ball position. Single-hidden-layer FFNN trained on 2.4M frames, then post-hoc multiplied by a goal-distance gradient because the network alone doesn't capture the "closer to opponent goal = more valuable" property at scale.

**Quality of Owned Space ($Q$).** Multiplication: $Q_i = PC_i \cdot V$. The state variable for the off-ball metrics.

**SOG.** Mean change in $Q_i$ over a 3-second window; thresholded by $\epsilon$. Split into *active* (player moving > 1.5 m/s) and *passive*. The passive channel catches Messi-walking-into-space.

**SGG.** Four geometric conditions on the (generator, receiver, defender) triple: defender originally near receiver, defender ends near generator, defender no longer near receiver, defender closed at least $\alpha$ distance to generator. Plus receiver $G_{i'}(t) \geq \epsilon$.

## Key methodological points

- **Pitch value is circular for defensive evaluation.** Trained on defender positioning. Using it to evaluate defenders evaluates whether they behave averagely, not whether they behave well.
- **No outcome grounding.** "Value" never connects to goals, xG, or possession outcomes. It's a *structural* notion of value (where defenders cluster, normalised by goal proximity), not a predictive one.
- **Hand-set hyperparameters carry the model.** $\delta = 5$m, $\alpha = 3$m, $w = 3$s, $\epsilon$ unspecified, the [4,10]m influence radius range — all calibrated by FCB analyst opinion, no robustness analysis.
- **One-match empirical case.** The Messi-walks-into-space narrative is a single-game observation.
- **First-to-arrive logic survives in modified form.** The Gaussian formulation softens it but still bakes in "closer + faster = more control."

## Where the model breaks

**Pitch control is a *local* model. Defensive contribution is often *non-local*.**

Two scenarios that share this structural failure:

1. **Cover shadow.** Defender presses ball carrier with body angled to occlude a passing lane. The would-be receiver has high pitch control of their patch, but is unreachable. The defender's contribution is geometric occlusion, not proximity. Pitch control under-weights this.

2. **Stepping up to play offside.** Defender moves *away* from an attacker to push the line forward. The attacker's local pitch control increases. The model registers a defensive *loss*. Reality: defender nullified the attacker entirely. Sign error, not just magnitude error.

Both cases: defensive value exerted at a distance from the defender's body. Pitch control's Gaussian-influence formulation centres every player's contribution on their own location and cannot capture this.

**Closing extensions:**
- Cover shadow → evaluate control along passing trajectories, not just at locations. $V(p) \cdot R(p \mid p_b)$ where $R$ is reachability from current ball position. Spearman 2018 and SkillCorner work in this direction.
- Offside → hard mask on $V(p)$ beyond the defensive line. Can't be soft because offside is binary and non-local.

## Where SGG misattributes credit

Four geometric conditions can fire while the football is illegitimate. Failure modes cluster:

| Failure mode | Family A patchable? | Patch |
|---|---|---|
| Independent ball-tracking | Yes | Defender velocity vector alignment toward generator at $t$ |
| Zonal rotation | Yes | Same as above |
| Reverse causation (receiver moved first) | **No** | Requires temporal/causal model |
| Zonal hand-off (replacement marker) | Yes | No-replacement-marker check at $t+w$ |
| Unreachable freed space | Yes | Ball-reachability check on freed space |
| Offside | Yes | Onside check on receiver |

Family A patches reduce false-positive rate but don't establish the causal claim. The paper's attribution language ("we are attributing space gain to a player when…") is a causal claim with no causal identification strategy. Pure geometry makes SGG a *less noisy descriptive correlation*, not a *causally identified attribution*. This is a wedge for econometric methods to enter the field.

## What survives if you only have attacker tracking

Stress test of the framework's commitments:

- $I_i$ for attackers — fully survives. Gaussian construction is per-player.
- $\sum_i I_i$ — survives. Unilateral influence sum, not pitch control.
- $PC$ — dies. The team-difference construction requires both teams.
- $V$ — dies as defined.
- $Q$, SOG, SGG — die (cascade).

Substitutes for $V$:
- Shot-xG-at-location: outcome-grounded but static (no ball-position conditionality).
- Outcome-success-at-location (xT-style): outcome-grounded, dynamic if propagated through transitions.
- Both lose ball-position conditionality unless explicitly constructed as $V(p \mid p_b)$ — which is what Spearman/OBSO formalises.

Substitutes for $PC$ (event-data inference) are structurally weaker — selection bias from attacker decisions, sparsity, and they reconstruct a worse version of pre-tracking-era pass models.

## What the paper actually contributes (ranked)

1. **Pitch control formulation** with motion + ball-distance. Durable. Used or compared-to in nearly all subsequent tracking papers, including Brefeld et al. (2021) which we read this week.
2. **SGG construction**. Conceptually novel relational credit assignment, but heavily hand-parameterised.
3. **Framing**. Off-ball value as a continuous spatial field over time. Genuine paradigm shift even where specific constructs don't hold up.

## Connections to be made forward

- **Spearman 2018 (next reading)** formalises ball-position-conditional, outcome-grounded value — the natural closing extension to Wide Open Spaces' value model.
- **SkillCorner progressive passing** formalises trajectory-based value and reachability — closes the cover-shadow gap.
- **Brefeld et al. 2021** extends the pitch control side specifically — data-driven movement models replacing the parametric Gaussian.
- **Ghosting (Le et al. 2017)** addresses defensive evaluation via counterfactual defender positioning — gestures at Family B fixes for SGG-style attribution problems.

## Logged for OPEN_QUESTIONS.md

1. Symmetric defensive credit assignment: SGG/SGL formulation that isn't circular with the value model. Unsolved in this paper and in the literature broadly.
2. Predictive validation of SOG/SGG: does player SOG over a window predict subsequent xG / shot creation? Candidate portfolio question.