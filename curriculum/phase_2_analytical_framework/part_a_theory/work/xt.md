# xT — Expected Threat

**Source:** Karun Singh (2018). *Introducing Expected Threat (xT).* [karun.in/blog/expected-threat.html](https://karun.in/blog/expected-threat.html)

---

## What xT is

A framework for valuing on-ball actions in soccer by computing a value surface over a discretized pitch. Every zone of the pitch is assigned a threat value representing the probability of scoring within the next ~5 actions given possession in that zone. An action's value is the change in the value surface between its start and end zones.

xT was published as a public blog post, not a peer-reviewed paper, and became one of the most influential pieces in public football analytics — partly because of its conceptual elegance, partly because of its computational simplicity, and partly because it produces a metric that is fully interpretable end to end.

---

## The core idea: location-based threat as a Markov chain

The defining commitment of xT is that **threat is a property of a zone**, not of the action that produced the situation. Singh's framework requires that an action's value depend only on the start and end locations — independent of who took the action, what happened before, or what happens after.

This is a deliberate simplification. It rules out a lot of football reality but produces a model with closed-form mathematical structure.

### The four empirical quantities

For each zone $(x, y)$ on a 16×12 grid, four quantities are estimated from event data:

- $s_{x,y}$ — probability of shooting from this zone (vs moving the ball)
- $m_{x,y} = 1 - s_{x,y}$ — probability of moving the ball
- $g_{x,y}$ — probability of scoring conditional on shooting from this zone (a crude xG)
- $T_{(x,y) \to (z,w)}$ — transition matrix: probability of moving the ball from $(x,y)$ to each destination zone $(z,w)$

These are pure aggregations from data. No model fitting, no parameters to tune.

### The recursive value definition

The value of zone $(x, y)$ is defined recursively:

$$xT_{x,y} = (s_{x,y} \times g_{x,y}) + \left(m_{x,y} \times \sum_{z=1}^{16} \sum_{w=1}^{12} T_{(x,y) \to (z,w)} \times xT_{z,w}\right)$$

Reading this:

- The **shoot path:** probability of shooting × probability of scoring if you shoot
- The **move path:** probability of moving × expected value of where you'll move to

The second term sums over all 192 destination zones, weighted by how often the ball typically goes from $(x,y)$ to each one. The destination value is itself $xT$, which makes the equation recursive.

### Iterative solution and its interpretation

The recursion is solved iteratively. Initialize $xT_{x,y} = 0$ for all zones, then update each iteration using the previous iteration's values. After 4–5 iterations, values converge.

The iterative process has a clean interpretation: at iteration $n$, $xT_{x,y}$ represents the probability of scoring within the next $n$ actions from zone $(x,y)$.

- **Iteration 1:** The move term zeros out, so $xT_{x,y} = s_{x,y} \times g_{x,y}$. This is essentially a shot-only model — value is meaningful only in zones where shooting and scoring happen, primarily the central penalty area. Value across most of the pitch is negligible.
- **Iteration 2:** Allows for "move once, then shoot." Value spreads to zones whose typical transitions reach the box.
- **Iteration 3:** Allows for "move, move, shoot." Value spreads further from goal.
- **At convergence:** Value has propagated all the way back to the defensive third, decreasing monotonically with distance from goal.

This iteration-by-iteration interpretability is one of xT's strongest features. The value at any zone has a precise meaning in terms of action horizons.

---

## Action valuation

Once xT is computed for every zone, action valuation is trivial:

$$V(\text{action}) = xT_{\text{end zone}} - xT_{\text{start zone}}$$

A pass that moves the ball from a zone with $xT = 0.05$ to a zone with $xT = 0.15$ has value 0.10. A backwards pass to a zone of lower value has negative xT.

Applied to the Özil-Kolašinac sequence Singh uses to motivate the post: Özil's pass moves the ball from $xT = 0.077$ to $xT = 0.158$ (delta +0.081), while Kolašinac's cutback moves it from $xT = 0.158$ to $xT = 0.171$ (delta +0.013). xT credits Özil with 86% of the build-up value.

### Path-independence as the central property

A direct consequence of the action-value formula is **path-independence**. The total value of moving the ball from zone A to zone Z equals $xT_Z - xT_A$, regardless of:

- How many actions it took to get there
- How many players were involved
- What route the ball travelled

This is mathematically clean — Singh draws the analogy to conservative forces in physics, where work depends only on start and end points. It is also a real loss in football realism. xT cannot distinguish:

- A patient five-pass build-up from a single long ball, when both end at the same zone
- A solo dribble through three defenders from a simple pass, when both end at the same zone
- A team that progresses via wide play from one that progresses centrally, when both arrive at the same final zone

It also implies that **moving the ball in a loop has total value zero**, even if the loop drew defenders out of position.

Whether path-independence is a feature or a bug depends on what you're using xT for. For team-level threat creation it's defensible — the total work of moving the ball is captured, distributed across whoever touched it. For per-action player evaluation it systematically underweights players who do hard things along the way.

---

## What xT does not do

The structural simplicity that makes xT elegant also produces a long list of limitations.

### Defensive contribution is not modeled

There is no $P_{concedes}$ analogue in xT. The framework values offensive build-up only. Defensive actions — tackles, interceptions, clearances, blocks — produce no xT directly. Extensions exist (xT against, xRisk, xTT) that bolt on a defensive component, but they're additions to the original, not part of it.

### State is reduced to location alone

The state space is 192 zones. Two passes that originate from the same zone and end in the same zone are valued identically — regardless of action type, body part, time elapsed, score, opponent, who's on the ball, or what the recent action history was.

This is a *much* sparser state representation than VAEP's 151-feature state. The same pass under high press and the same pass with no opposition have the same xT. The same shot from the spot in the 1st minute and in the 90th minute have the same xT contribution.

### No action-type sensitivity

A pass and a dribble from zone A to zone B have the same value. The transition matrix $T$ doesn't distinguish between them. Singh notes this could be extended; the basic model doesn't extend it.

### Turnovers are excluded by default

The original xT considers only successful moves. Failed passes, interceptions, dispossessions are not part of the transition matrix. This understates the cost of risky actions — a long progressive pass that has a 30% chance of being intercepted is valued the same as a safe pass to the same destination, because the failed cases don't enter the model.

### No game-state context

Time, score, match situation, opponent identity — none of it enters the model. xT in the 89th minute when chasing a deficit is the same as xT in the 5th minute of an even game.

### Off-ball actions are invisible

Same as VAEP. Event data only records on-ball events. A striker's perfectly timed run that creates the space for a through-ball produces no xT directly — the passer gets credit for the through-ball, the runner gets nothing for the run.

### Sparse-zone estimation problems

The 192-zone grid is a fine resolution for high-traffic areas (midfield, attacking third) but produces sparse estimates for rarely-occupied zones (touchlines far from goal, corner areas). $g_{x,y}$ in particular is estimated from very few shots in low-frequency zones. The recursive solve then propagates these noisy estimates through the surface — every upstream zone's value depends partly on noisy downstream estimates, contaminating the map. Standard fixes (regularization, smoothing) aren't part of the original implementation.

### The transition matrix is most of the model

The 192 × 192 transition matrix has ~37,000 entries, most estimated from limited data. Many entries are zero in finite samples (no observed pass from zone X to zone Y in the data), which the model treats as "transition impossible" rather than "transition unobserved." This is sparsity dressed as structural assumption.

### xT is descriptive, not prescriptive

xT values zones based on **what teams actually do**, weighted by empirical frequencies — not what they *should* do under optimal play. A zone's xT reflects the average historical productivity of possession in that zone, given how teams typically play from there. It does not tell you the value of being in that zone if everyone played optimally.

---

## Per-team xT

Because $s$, $m$, $g$, $T$ are all empirical, you can compute team-specific xT surfaces by restricting the data to a single team. Singh shows that Manchester City and Spurs have similarly *shaped* surfaces (both teams find roughly the same areas threatening) but City's values are uniformly higher.

The naive interpretation Singh gives is that City converts possessions into goals at a higher rate. The fuller interpretation is that **all four quantities can vary by team**, and the recursion magnifies any of them:

- $g_{x,y}$ may be higher (better shot quality / finishing from each zone)
- $s_{x,y}$ may be higher in valuable zones (more willingness to shoot from threatening positions)
- $T_{(x,y) \to (z,w)}$ may concentrate more probability on dangerous destinations (better build-up patterns)

The transition matrix differences are typically the most underappreciated source of per-team variation. A team whose typical pass from zone X reaches a high-xT destination will have higher xT *at zone X* than a team whose typical pass goes to a moderate-xT destination — even if both teams have identical shot conversion. This is why per-team xT differences propagate backwards through the pitch: it's not just about finishing, it's about transition behavior.

A counterintuitive consequence: a direct team (long balls, few touches) may have *higher* own-half xT than a possession team, because their typical transition from a deep zone goes to a high-xT destination, even though they spend less time progressing through midfield. xT values potential, not patience.

---

## Why xT survives despite VAEP

Three reasons for xT's continued relevance, even after more sophisticated models exist:

1. **End-to-end interpretability.** Every quantity in the model has a real-world meaning. $s$, $m$, $g$, $T$ are all empirical frequencies. The iteration count maps to action horizons. A coach asking why a player's rating is what it is can be answered in plain language, traced back to specific transitions in the data. VAEP's 151-feature CatBoost model does not allow this.

2. **Cheap to compute.** A handful of empirical aggregations and an iterative solve. Variations (per-team, per-phase, per-opponent) are trivial — re-aggregate and re-iterate. VAEP requires training a gradient boosting model on millions of action-states for every variant.

3. **Defensible in conversation.** xT survives contact with skeptical practitioners — coaches, recruitment directors, scouts — because every number is traceable to a real frequency. This is a political property, not a statistical one, but it matters for whether a model gets used in clubs.

xT gets you most of the way to a possession value model with a fraction of the complexity of VAEP. For descriptive analytics — opponent profiling, build-up analysis, identifying threat-creation patterns — xT is often enough.

---

## xT and VAEP: where they differ

Both models address the same problem (valuing on-ball actions beyond shots) but make fundamentally different design choices.

| Axis | xT | VAEP |
|---|---|---|
| **State** | Pitch zone only (192 states) | Last 3 actions + 151 features |
| **Target** | $P(\text{score in next ~5 actions})$ | $P(\text{score})$ and $P(\text{concede})$ in next 10 actions |
| **Horizon** | Implicit, set by convergence (~5 iterations) | Hardcoded $k = 10$ actions |
| **Architecture** | Markov chain + value iteration | Two CatBoost classifiers |
| **Credit** | $\Delta$ in zone values | $\Delta$ in learned probabilities |
| **Defensive contribution** | Not modeled | Modeled as $-\Delta P_{concedes}$ |
| **Action-type aware** | No | Yes |
| **Path-independent** | Yes | No |
| **Interpretability** | High | Low |
| **Compute cost** | Low (analytical solve) | High (model training) |

The deepest contrast: **xT is a constructed value function; VAEP is a learned one.** xT computes value deterministically from empirical aggregations and the Bellman recursion. VAEP fits a classifier to predict an outcome and uses its predictions as the value function. This is the difference between value iteration on a known MDP and value estimation via supervised learning.

Path-independence vs path-dependence is the cleanest concrete consequence of this contrast. xT can't see the difference between a Messi dribble and a target-man hold-up at the same zone. VAEP, because its state includes recent action history, can.

xT is to VAEP what a linear regression is to a deep neural network: less expressive, far more interpretable, easier to debug, faster to compute, and surprisingly competitive on the descriptive tasks it's designed for.

---

## Bottom line

xT's lasting contribution is the recognition that threat can be modeled as a property of pitch location, computed via a Markov chain over an empirical transition structure. The model is mathematically elegant, fully interpretable, and computationally cheap. Its weaknesses are exactly the weaknesses of its simplicity: no defensive contribution, no action-type sensitivity, no game-state context, path-independence, and noisy estimates in low-frequency zones. Subsequent models (VAEP, OBV, EPV) address one or more of these limitations at the cost of interpretability and compute.

xT is best understood as a **descriptive tool for build-up play**, not a complete possession value framework. Within that scope, it remains one of the most useful and most-deployed metrics in the public football analytics ecosystem.