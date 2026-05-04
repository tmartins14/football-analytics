# EPV — Decomposing the Immeasurable Sport (Fernández, Bornn, Cervone, 2019)

**Paper:** Fernández, J., Bornn, L., Cervone, D. (2019). *Decomposing the Immeasurable Sport: A Deep Learning Expected Possession Value Framework for Soccer.* MIT Sloan Sports Analytics Conference. [PDF](https://www.lukebornn.com/papers/fernandez_sloan_2019.pdf)

The 2021 *Machine Learning* follow-up (Fernández, Bornn, Cervone) introduces SoccerMap and provides component-level validation.

---

## The conceptual jump

xT and VAEP are **action-valuation** models — value is computed at action moments. EPV is a **state-valuation** model — value is computed at every frame, on-ball or off-ball. Action values become a derived quantity (the change in EPV between frames), not the fundamental object.

EPV is defined in $[-1, 1]$:
- $+1$ = goal for the attacking team
- $-1$ = goal for the defending team after immediate possession regain
- Values in between = expected goal differential

The signed expectation lives in the state itself. A possession with EPV = -0.09 means the model thinks the defending team is more likely to score next, even though the attacking team has the ball.

This is enabled by tracking data: (x, y) positions and velocities of all 22 players plus the ball at 25 frames per second. Event-based models cannot do continuous state valuation because event data only records on-ball moments.

---

## The decomposition

The methodological core. EPV is computed as:

$$\text{EPV}(t) = \sum_{A \in \{\text{pass, shot, ball-drive}\}} P(A | t) \cdot E[\text{outcome} | A, t]$$

Passes are further decomposed into success and turnover paths:

$$\text{Pass value} = P(\text{success}) \cdot E[\text{value} | \text{success}] + P(\text{turnover}) \cdot E[\text{value} | \text{turnover}]$$

Each component is a separate model — mostly deep neural networks producing **value surfaces** over the whole pitch. Pass and turnover probabilities use logistic regression. Action likelihood uses CNNs over pitch control surfaces.

### Why decomposition matters

1. **Per-component interpretability.** Each component produces a football-meaningful intermediate output (a heatmap, a probability distribution) that's inspectable independently of the EPV calculation.

2. **Structural prior.** The decomposition encodes football logic — "EPV depends on which action happens next, weighted by its probability." This both helps learning (denser per-component training signal) and constrains what relationships the model can find. Useful prior when football logic is correct; limiting when it isn't.

3. **Multi-purpose analytical capability.** This is the most consequential reason. Each component is a separate analytical tool. The risk-reward decomposition (plotting reward against risk for each pass) is only possible because risk and reward exist as separate model outputs. An end-to-end EPV model couldn't produce it.

---

## Dynamic pressure-line zones

EPV uses dynamic relative location based on opponent formation lines, not absolute pitch coordinates. Spectral clustering on defending players' X-coordinates produces three pressure lines (forwards, midfielders, defenders), defining four zones (Z1-Z4) that move with the opponent's shape.

This is the framework's answer to a structural critique of xT/VAEP: **football tactics are about relative positioning, not absolute locations.** A pass breaking the first pressure line is tactically meaningful regardless of absolute pitch location.

The implementation has limitations — three-cluster assumption breaks for asymmetric or transitional formations, the 2-second window misses fast pressure transitions, horizontal-line model misfits diagonal pressing. Better than xT's static grid, but still a choice with assumptions.

---

## What EPV unlocks

**Off-ball valuation.** EPV computes value surfaces over the whole pitch. Teammates in high-value regions are creating value through positioning, even if they never receive the ball. Structurally impossible with event data.

*Important caveat:* the paper's off-ball analyses sample only at on-ball action moments. This captures **position-at-action-time**, not **trajectory-leading-to-action-time**. The "move before the move" — runs that drew defenders out of position seconds before, structural rotations that maintained shape — is not captured. Fully off-ball valuation would require continuous frame-level evaluation, counterfactual attribution of surface changes to specific player movements, and integration over time. The framework supports this in principle; the paper's analyses don't implement it.

This matters most for positional play (Cruyff/Guardiola school), where off-ball value lives in continuous structural maintenance rather than action-adjacent positioning. EPV captures decisive runs; it misses sustained structural work.

**Risk-reward decomposition.** Reward (EPV given pass success) and risk (EPV given turnover) are separate model outputs. Players' decision-making profiles can be characterised by where they sit in risk-reward space.

**Counterfactual best-action analysis.** EPV computes the value of the action taken *and* the best alternative. Event-based models can't do this. The implementation evaluates discrete alternatives (best pass to each teammate, etc.), not the continuous space of all possible actions.

---

## What EPV commits to

The continuous frame-by-frame evaluation makes claims the paper takes for granted:

1. **Smoothness** — small position changes produce small EPV changes. Football has discontinuities (a defender stepping into a passing lane is binary, not smooth) the assumption averages over.
2. **Real off-ball value at frame timescales** — frame-to-frame EPV changes reflect signal, not noise. The paper doesn't validate signal-to-noise at frame resolution.
3. **Calibration across the full state space** — EPV evaluates configurations that may be rare or out-of-distribution. Not addressed.
4. **Markov assumption at frame level** — state alone determines expected outcome; path-dependent effects (momentum, recent 1v1 outcomes) are invisible.
5. **Unsolved attribution at frame resolution** — EPV changes continuously; which players caused which changes is not formally answered.

These aren't necessarily wrong, but a user should know which assumptions they're trusting.

---

## Other limitations

- **Tracking data dependency.** Present-tense barrier to adoption — most leagues have only event data.
- **Missing body orientation.** Tracking captures position, not body shape, head direction, or eye gaze. The Sergi Roberto example in the paper acknowledges this.
- **Average-player modelling.** Messi keeping the ball is modelled the same as a youth player keeping the ball.
- **Limited validation in the 2019 paper.** Extensive case studies, no split-half robustness, no comparison metrics. The 2021 paper does more but no controlled head-to-head against xT/VAEP exists in the literature.
- **Interpretability is framework-level, not component-level.** Better than VAEP at the framework level (visual surfaces, separable components), worse than xT at the component level (deep nets vs. explicit empirical aggregations).

---

## Mapped onto the five design axes

| Axis | EPV |
|---|---|
| **State** | Tracking data: positions and velocities of 22 players + ball, every frame. Plus dynamic pressure-line context. |
| **Target** | Continuous expected goal differential, frame-by-frame |
| **Horizon** | Possession-based, valued at every instant |
| **Architecture** | Decomposed component models fused via stochastic process |
| **Credit** | Δ in EPV between frames; applies to actions and off-ball positioning |

| | xT | VAEP | EPV |
|---|---|---|---|
| **Input** | Event | Event | Tracking |
| **State richness** | Pitch zone | 3 actions + 151 features | Full spatial config |
| **Time resolution** | Action | Action | Frame (25 Hz) |
| **Off-ball valuation** | No | No | Partial |
| **Risk-reward decomposition** | No | Net only | Yes |
| **Counterfactuals** | No | No | Yes (discrete) |
| **Interpretability** | Component-level high | Low | Framework-level high, component-level low |
| **Robustness validated** | Yes (0.89) | Yes (0.25) | No |
| **Data accessibility** | Universal | Universal | Restricted |

EPV occupies a different region of the design space than the event-based models — most ambitious in scope, most demanding in input data. Not a strict improvement over xT/VAEP; operates under different constraints and serves different use cases.

---

## Bottom line

EPV's three lasting contributions: **continuous frame-by-frame valuation** replacing action-based valuation; **decomposed component models with visual surfaces** replacing scalar action values; **tracking-data input** replacing event data. Together these enable off-ball valuation, risk-reward decomposition, and counterfactual analysis — capabilities structurally impossible with event-based models.

The framework has real limitations the paper underplays: off-ball analyses sample at on-ball moments and miss continuous structural play; frame-level evaluation makes commitments the paper doesn't validate; tracking data dependency is a present-tense barrier; no controlled comparison against xT/VAEP exists. EPV is the natural ceiling for action-valuation given current optical tracking data — a major waypoint, not the endpoint.