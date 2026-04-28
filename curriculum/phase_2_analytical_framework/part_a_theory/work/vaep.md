# VAEP — Valuing Actions by Estimating Probabilities

**Paper:** Decroos, Bransen, Van Haaren, Davis (2019). *Actions Speak Louder Than Goals: Valuing Player Actions in Soccer.* KDD '19. [arXiv:1802.07127](https://arxiv.org/abs/1802.07127)

---

## What VAEP is

A framework for assigning a single number — in expected goal units — to every on-ball action in a soccer match, capturing both offensive contribution and defensive contribution. The framework is paired with **SPADL** (Soccer Player Action Description Language), a vendor-agnostic standardized representation of player actions that VAEP consumes as input.

VAEP's contribution is not the deepest model in the field. Its contribution is the framework, the open-source release (`socceraction`), and the standardization that made action valuation reproducible.

---

## The core idea: value = change in state probability

The defining commitment of VAEP is that an action's value is **the change it produces in two probability functions over game states**.

For each game state $S_i$ (defined as the last three actions up to and including $a_i$), VAEP estimates:

- $P_{scores}(S_i)$ — probability the team in possession scores in the next 10 actions
- $P_{concedes}(S_i)$ — probability the team in possession concedes in the next 10 actions

The value of action $a_i$ is:

$$V(a_i) = [P_{scores}(S_i) - P_{scores}(S_{i-1})] - [P_{concedes}(S_i) - P_{concedes}(S_{i-1})]$$

$$V(a_i) = \Delta P_{scores}(a_i) - \Delta P_{concedes}(a_i)$$

### Why "change in state" is the key insight

This formulation is the part of VAEP that matters most, and it has several consequences worth holding onto:

1. **Credit goes to the action that moved the probability, not the action that ended up in the dangerous state.** A line-breaking pass that switches the ball into the final third receives a large $\Delta P_{scores}$. A 5-yard square pass at the edge of the box that immediately precedes a tap-in may receive less VAEP than the pass before it, because the dangerous state was already established.

2. **Credit is forward-looking and local.** Each action is valued by what it changed *at that moment*, given the current state. Past actions are not retroactively re-credited based on what happens later. If pass 1 in your own half is followed nine actions later by a turnover, pass 1 receives ~0 VAEP. The turnover action absorbs the negative value because that's where the state change happens.

3. **The Markov assumption.** VAEP assumes the probability of future outcomes from a state is a sufficient statistic for valuing the action that produced that state. The depth-3 state representation embeds a tactical-memory assumption: anything beyond the last three actions is treated as not relevant to the value computation.

4. **Movement, not endpoints.** VAEP rewards progressive actions that change the probability function, not actions that simply occupy threatening locations. This is fundamentally different from xT, which assigns value based on location transitions in a stationary Markov chain.

---

## The two-model approach: $P_{scores}$ and $P_{concedes}$ separately

VAEP trains two independent classifiers rather than one model predicting net goal differential.

### Why the split matters

**Specialized features.** The features that predict scoring (distance to opponent goal, action type at the attacking end, attacking momentum) are not the same as the features that predict conceding (distance to own goal, defensive disorganization, recent turnover risk). Two models can each focus on their respective signal without compromise.

**Decomposition into offensive and defensive components.** Every player's total VAEP can be split into:
- Offensive VAEP — sum of $\Delta P_{scores}$ across their actions
- Defensive VAEP — sum of $-\Delta P_{concedes}$ across their actions

This decomposition is the analytical payoff of the two-model design. A holding midfielder might be neutral on offense but elite defensively. A creative #10 might be elite on offense and a liability defensively. A single model predicting net differential collapses this distinction.

**Every action is evaluated by both models.** This is a point worth being explicit about: actions are not routed to one model or the other based on whether they "look offensive" or "look defensive." A shot has both $\Delta P_{scores}$ (likely large positive) and $\Delta P_{concedes}$ (likely near zero, since the ball is at the opposite end). A clearance has both $\Delta P_{scores}$ (likely small) and $\Delta P_{concedes}$ (likely large negative — risk reduced). Both deltas always exist; the model just outputs whichever values the data implies.

### What the split costs

**No joint calibration.** The two models are trained independently with no shared loss. There is no guarantee that "+0.05 offensive value" is comparable in scale to "+0.05 defensive value." Their calibration depends on the separate training of each classifier.

**$P_{concedes}$ is empirically harder to estimate.** Conceding depends heavily on what the *opponent* does next, which event-based features capture only indirectly. As a result, defensive VAEP estimates carry more noise than offensive VAEP estimates. Defenders' ratings — which are dominated by $\Delta P_{concedes}$ — are inherently less trustworthy than attackers' ratings.

**No exploitation of correlations between the two probabilities.** End-to-end games push both probabilities up. Cagey games push both down. A joint model could learn this; two independent models cannot.

---

## What VAEP does not do

This is where most of the legitimate critique of VAEP lives. The framework is consistent and reproducible, but the limits are real.

### It only values on-ball actions

VAEP can only value what SPADL records, and SPADL only records on-ball events. A defender making a covering run that prevents a counter never enters the model. A striker making a perfectly timed run to receive a through-ball never enters the model — the *passer* gets the credit for the through-ball; the runner gets credit only when they touch the ball.

This is not a flaw in VAEP's design. It is a limit imposed by the data VAEP consumes. Off-ball valuation requires tracking data (player coordinates 25 times per second for all 22 players) and is a qualitatively different problem.

### It does not model counterfactuals

VAEP tells you what happened. It does not tell you what could have happened. A successful pass receives credit for the probability change it produced, but VAEP does not ask whether a better alternative was available. It rewards execution within the action that occurred, not decision quality across the choice space.

### It is barely opponent-aware

The features include game state (score, time, location) but not opponent identity, opponent tactical setup, or opponent player positions. The model is trained across many games and many opponents, so it implicitly averages over opponent quality. The same action against different defensive structures has different real-world value, but VAEP does not capture this directly.

### It does not learn within a match

VAEP is trained offline. At inference time, it evaluates each state using fixed parameters. It does not adapt to how a particular game is unfolding. If a state's $P_{concedes}$ is high during a match, that is because the model evaluates that *type* of state as dangerous, not because it has detected that today's opponent is dominating.

### The hyperparameters are modeling commitments, not noise reduction

Two choices to be conscious of:

- **Horizon $k = 10$ actions.** This determines how far forward the target looks. Smaller $k$ approaches xG-style attribution (only late actions get credit). Larger $k$ credits actions further back at the cost of attribution noise. $k = 10$ is a defensible compromise but it is not optimal; it is a commitment to a particular bias-variance tradeoff.

- **State depth = last 3 actions.** This is a Markov assumption. Anything beyond three actions back is invisible to the state representation. Pressing triggers, set-piece routines, and longer tactical patterns whose relevant context exceeds three actions are systematically underrepresented.

### The binary label is a foundational limitation

VAEP trains on the label "did a goal happen in the next 10 actions, 0 or 1?" The classifier learns to predict the probability that this binary outcome is 1.

Three problems with this:

1. **The label is a single Bernoulli realization of the probability you actually want to estimate.** With enough data this converges, but goals are rare (~1–2% of state transitions) so the positive signal is sparse.

2. **The 10-action cutoff creates label cliffs.** A goal at action 11 contributes 0 to the label for action 1, even though action 1 may have been part of the buildup.

3. **Near misses are invisible.** A sequence ending in a post-strike, two saves, and a blocked shot has the same label (0) as ten sideways midfield passes. The classifier learns from them as if they are equivalent.

A more rigorous formulation would predict expected goal value of the sequence directly (continuous target), or use survival/hazard models to avoid the fixed cutoff, or use temporal-difference value estimation from RL. The binary classifier is a pragmatic choice, not a principled one.

---

## How to evaluate models that come after VAEP

VAEP is the reference point in this literature. Every subsequent action-valuation model — xT, OBV, g+, EPV, deep-learning on-ball value — can be mapped against five design axes, and the differences across the literature are differences along these axes:

| Axis | What VAEP commits to | What other models change |
|---|---|---|
| **State representation** | Last 3 actions, event data | Tracking data, pitch control, full possession |
| **Target** | Binary "goal in next 10 actions" | Continuous xG sum, expected possession value, hazard rate |
| **Horizon** | Fixed 10-action window | Variable, full match, decaying weights |
| **Architecture** | Two independent classifiers | Joint models, end-to-end RL value functions |
| **Credit assignment** | Marginal delta per action, Markov | Shapley, counterfactual rollouts, off-policy estimators |

Reading a new paper, the first question to ask is: which of these axes did they change, and what does that change buy them — and cost them — relative to VAEP?

---

## Bottom line

VAEP's lasting contribution is that it transformed action valuation from a subjective task into a probabilistic prediction task with a clear formula and a reproducible pipeline. Its strength is in the framework — the change-in-state formulation, the two-model decomposition, the open-source release. Its weaknesses are visible exactly because the framework is so explicit: the state is impoverished (no off-ball, no opponent, no counterfactual), the target is coarse (binary, fixed horizon), and the architecture is loose (no joint calibration). Subsequent literature in this space is mostly a response to one or more of those weaknesses.