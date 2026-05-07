# Beyond Expected Goals (Spearman, 2018)

**Source:** MIT Sloan Sports Analytics Conference 2018. PDF historically at sloansportsconference.com (currently inaccessible via direct fetch); secondary references widely available.

## What the paper does

Constructs the first formal probabilistic decomposition of off-ball scoring value: $\text{OBSO} = P(\text{score} \mid r) \cdot P(\text{control}_i \mid r, t) \cdot P(\text{transition to } r \mid t)$. Three outcome-grounded factors, multiplied. Score × control × transition is now the standard mental decomposition for any spatial scoring-opportunity model.

Trained on 58 matches, one professional league, 2017-18. Stronger empirical foundation than WOS but still not multi-league validated.

## Framework on the five design axes

| Axis | OBSO |
|---|---|
| **State** | Full 22-player + ball spatial configuration; tracking + event data |
| **Target** | $P(\text{player } i \text{ scores next} \mid r, t)$ — outcome probability |
| **Horizon** | Up to next on-ball event |
| **Architecture** | Multiplicative: physics-based PPCF × static score model × empirical transition model |
| **Credit assignment** | Per-player, per-location surface (heatmap, not scalar) |

Compared to WOS: same State axis, dramatically different Target (outcome-grounded vs structural), same Horizon roughly, similar Architecture in being decomposed but each component does something different.

## Component breakdown

**$P(\text{score} \mid r)$ — Score model.** Static, location-only. Trained on shot data. Asymmetry with the rest: the other two components are dynamic (configuration-conditional), this one isn't. Load-bearing simplification that the paper doesn't fully defend.

**$P(\text{control}_i \mid r, t)$ — PPCF.** Physics-based pitch control. ODE system: each player's control accumulates as a Poisson process, weighted by probability of reaching $r$ within time $T$. Uses aerodynamic drag for ball flight time — meaningful divergence from WOS's instantaneous-ball assumption. Higher computational cost.

**$P(\text{transition to } r \mid t)$ — Transition model.** Empirical distribution over next-event-locations given current ball position and game state. Most data-hungry component, often simplified in implementations to distance-based priors.

## Key methodological points

- **Outcome-grounded throughout.** Every component connects to scoring probability. Compare WOS where "value" is structural (defender clustering × goal proximity).
- **Multiplicative form assumes independence between components.** All three pairs are actually coupled in reality:
  - Transition depends on control (passers route to controllable receivers)
  - Control depends on transition (pass type affects receiving probability)
  - Score depends on transition+control (configuration at arrival affects shot quality)
  - Multiplicative form is a deliberate tractability simplification, not a claim about true independence.
- **Static score model averages over within-location configuration variance.** Defensible when configuration variance is small relative to location variance; breaks in tails (counter-attacks, GK out of position, high-leverage moments where player evaluation depends on tail performance).
- **Computational cost is real.** ODE-based PPCF is expensive at scale. Limits real-time deployment.
- **Transition model is brittle.** Empirical kernels don't generalise across team styles; many implementations substitute simpler priors and degrade the metric's outcome-probability claim.

## What's actually in common use

- **PPCF**: yes, foundational. One of the two dominant pitch control implementations (alongside Fernández-Bornn). Heavy public uptake via Friends of Tracking tutorials.
- **OBSO as a metric**: more academic uptake than SOG/SGG, but still mostly research. Key barrier: it's a *surface* per player per frame, with no canonical scalar aggregation. Metrics requiring contested aggregation choices struggle to deploy.
- **The decomposition framework**: heavily influential. Score × control × transition is now the standard mental decomposition.

## Tier-3 synthesis: the joint-credit gap

WOS's SGG attempts off-ball *creator* credit. OBSO assigns off-ball *receiver* credit. Neither captures that off-ball value is **jointly produced** — a coordinated movement involving 3-5 players, where credit needs to be decomposed across all contributors rather than attributed to a single named role.

Two distinct symptoms of the same underlying issue:

1. **Joint-production gap (Q3).** A great off-ball sequence has ball carrier holding possession, runner pulling marker, third player attacking vacated space, possibly a fourth pulling defenders to one side. SGG captures one role (dragger). OBSO captures another (final receiver). Neither attempts the joint decomposition.

2. **Role-multiplicity gap.** A single contributor can occupy multiple roles or none of the named ones. Messi pulling four defenders is doing something neither SGG (which fires only when defenders end near the dragger) nor OBSO (which credits the eventual scorer) captures. Adding more named roles is whack-a-mole; the fix is to abandon role-based attribution.

**The structural answer:** off-ball value in football is inherently *relational*; current metrics treat it as *role-typed*. A relational view requires player-by-player marginal contribution, not role-by-role attribution.

## What a model that closes the gap would look like

Three candidate structures:

1. **Counterfactual / Shapley-style decomposition.** Compute play value with all actual movements, then sequentially replace each player's movement with a baseline and measure marginal drops. Each player's credit is their marginal contribution averaged over orderings. Cervone et al. did this for basketball; gestures exist in football but no scaled implementation.

2. **Cooperative game theory.** Frame off-ball contribution as coalition-formation; use Shapley value or related solution concepts to distribute total play value across involved players. Mathematically heavier; game-theoretically rigorous; connects directly to causal-econometrics + game-theory positioning.

3. **Movement-correlation models.** Decompose value by correlation structure of player movements with goal-creating sequences. Closer to plus-minus / RAPM in basketball; partly causal in spirit.

**Note on the counterfactual baseline problem.** All three approaches require defining "what would have happened without this player's action," which has no neutral choice — replace their movement with stillness (implausible), league average (whose?), personal historical pattern (circular if evaluating them). This is a deep methodological problem in causal attribution; football inherits it.

## Independence assumption — Q1 in detail

Three pairs of components, all coupled, all assumed independent:

| Dependency | Direction | Mechanism |
|---|---|---|
| Transition ↔ Control | Both ways | Passers choose targets based on receivability; pass type affects control probability |
| Score ↔ Transition | Score depends on transition | Through ball arriving at edge of box ≠ long ball at same location |
| Score ↔ Control | Score depends on control | Player on the run controlling vs static reception affects shot quality |

**Closing extension (formalised correctly this time):**
$$P(\text{score}, \text{control}_i, \text{transition}) = P(\text{score} \mid \text{control}_i, \text{transition}, r) \cdot P(\text{control}_i \mid \text{transition}, r, t) \cdot P(\text{transition} \mid r, t)$$

Chain rule applied to all three; no independence assumed. Empirically harder (joint distributions, more data) but principled. Worth estimating bias from multiplicative form before deciding if joint estimation is worth the cost.

## Static score model — Q2 in detail

The simplification: $P(\text{score} \mid r)$ replaces $P(\text{score} \mid r, \text{configuration})$ with the marginal averaged over configurations.

**When it holds:**
- Configuration is structurally constrained by $r$ (e.g., penalty area, defensive shape mostly determined)
- Configuration variance exists but doesn't move score probability much (e.g., midfield)

**When it breaks:**
- Configuration-space tails: rare configurations get absorbed into average — counter-attacks, broken defensive shape
- Score-space tails: high-leverage moments averaged with low-leverage at same location — GK out of position, shot from halfway

**Empirical test:** estimate $\text{Var}[P(\text{score}) \mid r, \text{config}]$ across configs holding $r$ fixed; compare to $\text{Var}[P(\text{score}) \mid r]$ marginal. Ratio measures information loss. Hasn't been done in public literature.

## Connections to be made forward

- **Brefeld et al. 2021 (next reading)** extends pitch control with data-driven movement models — adds the player-specific velocity component PPCF/Fernández-Bornn approximate with parametric assumptions.
- **SkillCorner progressive passing** formalises trajectory-based reachability and decision quality — bridges the static-vs-dynamic gap on opportunity adjustment.
- **Ghosting (Le et al. 2017)** uses counterfactual defender positioning — closest existing work to the Shapley-style attribution gap identified above.
- **Pearl's *Book of Why*** provides the conceptual scaffolding for counterfactual attribution — the gold standard for thinking through "what would have happened without this contributor's action."

## Logged for OPEN_QUESTIONS.md

1. **Joint off-ball credit decomposition.** Multi-year research direction, not portfolio question. Counterfactual / Shapley / correlation approaches all viable; baseline-choice problem is the load-bearing methodological issue.
2. **Normative-transition OBSO.** Replacing empirical transition model with optimal-pass model. Changes what OBSO measures (descriptive → prescriptive). Different question from empirical OBSO; not a free upgrade.
3. **Bias from multiplicative independence assumption.** Estimate magnitude of bias from independence assumption before deciding whether joint estimation is worth the data cost. Tractable as portfolio question with sufficient tracking data.
4. **Shot-given-arrival modelling.** Configuration-conditional score component for OBSO. Data-hungry beyond StatsBomb open data tier; requires multi-season multi-league aggregation.

## Methodological self-assessment from this session

**Improved:**
- Independently sketched outcome-grounded ball-position-conditional value before being shown OBSO formalisation (carryover from WOS chat).
- Identified one real dependency between transition and control on Q1, in the right direction.
- Pushed back on tutor when pushback became counter-productive — that's a meta-level tutoring control I hadn't exercised before. Worth keeping.
- Found the role-multiplicity insight on the Messi-pulling-four follow-up, independently extending the Q3 synthesis.

**Still showing:**
- First-plausible-intervention pattern: identified one dependency on Q1 (transition-control) and stopped before enumerating all three pairs.
- Answer-construction issue on Q2: committed to a position ("simpler is defensible") before working through the question's structure ("when does it break, when does it hold"). Required a redo.
- Conflated comparison-of-models with internal-consistency questions — answered "OBSO vs WOS" when asked about OBSO's internal simplification.
- Underused tutor-provided formal scaffolding — Q2 framework (variance decomposition) was given explicitly and not deployed.
- Synthesis answer on Q3 buried the strong observation (joint credit) next to a weaker one (intent), losing emphasis.

**Score:** 6.5/9 across three comprehension questions (Q1: 2.5, Q2 redo: 2, Q3: 2). Marginally better than WOS in absolute terms.

**Pattern to actively work against in Week 2 remainder:** when a question has structure ("when does X hold and when does it break?"), enumerate conditions before committing to a position. When given formal scaffolding by the tutor, deploy it.