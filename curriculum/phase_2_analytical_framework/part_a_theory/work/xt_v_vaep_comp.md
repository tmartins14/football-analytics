# Van Roy, Robberechts, Decroos, Davis (2020) — A Critical Comparison of xT and VAEP

**Paper:** Van Roy, M., Robberechts, P., Decroos, T., Davis, J. (2020). *Valuing On-the-Ball Actions in Soccer: A Critical Comparison of xT and VAEP.* AAAI-20 Workshop on Artificial Intelligence in Team Sports. [PDF](https://tomdecroos.github.io/reports/xt_vs_vaep.pdf)

---

## What the paper is

A controlled comparison of xT and VAEP — the two canonical action-valuation frameworks for soccer event data. Written by the VAEP team at KU Leuven (Decroos, Davis, plus collaborators Van Roy and Robberechts). The paper introduces no new model; it puts the two existing models side by side, on the same dataset (StatsBomb, EPL 2017/18 train, 2018/19 evaluate), and asks how their design choices lead to different action values, different player rankings, and different stability properties.

The authors are not unbiased — they built VAEP. The framing favours VAEP in the qualitative section (the cases they pick highlight what VAEP captures that xT misses). But the most important quantitative finding (xT is dramatically more robust than VAEP) is reported honestly and complicates any clean superiority claim.

---

## The unified frame

The paper's most useful contribution is a unified equation that both models fit:

$$V(a_i) = Q(S_i) - Q(S_{i-1})$$

Both xT and VAEP value an action by the change in some quality function $Q$ between the post-action and pre-action states. What differs across the two models is the state representation $S$ and the value function $Q$.

For xT: $S_i$ is the zone of the ball; $Q(S_i) = xT(\text{zone})$.
For VAEP: $S_i$ is the last 3 actions plus 151 features; $Q(S_i) = P_{score}(S_i) - P_{concede}(S_i)$.

Every action-valuation model in this lineage can be written this way. The first question to ask of any new model in this space is: *what is the state representation, and what is the value function?* Everything else (algorithm choice, feature engineering, hyperparameters) is downstream of those two decisions.

---

## The two design dimensions

The paper organises the comparison around two axes.

### Location-based vs feature-based state representation

xT represents a state purely as a pitch zone (192 zones on a 16×12 grid). VAEP represents a state as the last three actions plus a feature-rich description including action types, locations, body parts, time elapsed, and game context (score, time remaining, score differential).

Three concrete consequences of this difference:

**1. xT can only value ball-progressing actions.** Because the state is fully captured by the zone, an action that doesn't move the ball between zones has value zero by construction. Take-ons within a zone, defensive actions like tackles and interceptions, all clearances and blocks, short dribbles in the box that stay within a zone — all of these are assigned zero by xT. This is structural. No extension within a pure zone-based framework can change it without changing the state representation.

**2. VAEP captures action context.** A shot following a through-ball is a different state from a shot following a multi-defender dribble. xT cannot see this; VAEP can. This is what enables VAEP to value the same zone-to-zone transition differently depending on what came before.

**3. VAEP captures game context.** Time, score, score differential, match phase — none of these enter xT. A 90th-minute pass while chasing the game has the same xT as a 5th-minute pass in an even game. VAEP includes these features explicitly.

The cost of this richness: **VAEP is a black box, xT is auditable.** xT zone values decompose into explicit empirical components ($s$, $g$, $m$, $T$). VAEP predictions come from a 151-feature gradient boosted tree ensemble with no comparable transparency. SHAP-style attribution helps but doesn't fully close the gap.

### Possession-based vs window-based action sequencing

This distinction is the more important one and the one to internalise.

**xT is possession-based.** It models a state's value as the probability of scoring within the current possession. When the possession ends — by goal, by shot, or by turnover — the Markov chain hits an absorbing state. Goals are absorbing, but so are turnovers.

**VAEP is window-based.** It looks $k = 10$ actions ahead, regardless of which team has the ball. Possession changes don't reset the window. If your team loses the ball at action 3, action 4 is the opponent's possession, and what happens during that opponent possession is part of VAEP's training signal for the original action.

Two crucial consequences flow from this:

**VAEP captures risk.** A risky pass that has high upside if completed but exposes your goal if intercepted gets penalised by VAEP because the post-turnover continuations are part of the training data. xT cannot see this — once the possession ends, the chain absorbs and the post-turnover threat is invisible.

The training-data mechanism matters here, not just the structural one. VAEP's training data contains thousands of examples of (state → turnover → opponent counter → concession) sequences. The model learns that *certain features of states* correlate with concession events that occur after a turnover. xT's training data, being possession-bounded, structurally excludes this relationship — once the possession terminates, the data trail ends and the model cannot learn how features at the action's moment correlate with later concessions.

**VAEP can value failed actions.** A clearance kicked out of bounds (giving your team time to organise) is meaningfully different from a clearance that lands at the opponent's feet (giving them a quick attack). Both are losses of possession; both terminate xT's chain identically. VAEP, by tracking what actually happens in the next 10 actions, distinguishes them.

The window-vs-possession distinction is what enables VAEP to value defensive actions, risky decisions, and failed actions. It is a deeper consequence of the design choice than the two-model split (offensive/defensive components), and it's the structural reason VAEP is broader in scope than xT.

---

## The qualitative comparison: four action types

The paper picks four specific action categories and compares the value distributions each model assigns. Three of them showcase what VAEP captures that xT misses; the fourth is honest about ambiguity.

**Backward passes into the own penalty box (~19/match).** xT values these near zero — both start and end zones are low-xT, so the delta is negligible. VAEP assigns more diverse values, positive and negative, depending on context: a backward pass to a centre-back with space and time scores positive (low risk, opens future progression); a backward pass under pressure scores negative (high risk of opponent winning the ball in a dangerous area). xT cannot make this distinction. The risk dimension is invisible to it.

**First ball progression of a counter attack (~2-3/match).** When you recover the ball in your own half and immediately progress it, the *opponent is still in attacking shape*. The next 10 actions are far more likely to produce a shot than a normal possession from the same start zone. VAEP captures this because its window includes those next actions. xT cannot — its state is just the zone, regardless of recovery context. The paper shows VAEP values for these actions have higher mean and variance; xT values are heavily concentrated near zero.

**Forward dribbles inside the penalty box (~4/match).** xT's grid resolution hurts it here. Many dribbles in the box don't move the ball into a different zone — they rearrange position within a zone. xT assigns these zero by construction. But these dribbles can matter enormously: a dribble past a defender 6m from goal, even within the same zone, dramatically increases scoring probability. VAEP captures this because action type and fine-grained location are part of its state. This is a concrete cost of the location-only representation that's worth remembering.

**Forward passes to the border of the penalty box (~5/match).** This is the only category where xT looks better than VAEP — and the paper is honest about not knowing which is right. xT assigns higher values; VAEP discounts them. Two interpretations: xT might be capturing positional advantage well, or VAEP might be correctly discounting based on context (low completion rate, counter-attack risk) that xT misses. The paper concludes: "determining the ground truth of these action values is very difficult, if not impossible." **There is no oracle for action values.** When two models disagree, neither is the truth — there's no external benchmark. You can only ask which assumptions you trust for the use case.

---

## The quantitative comparison: player rankings

The paper rates every player in the 2018/19 EPL by both models and analyses the top 25 from each.

### Top rankings diverge

The Jaccard similarity between the top-25 lists is **0.48**. Less than half the players overlap. Eden Hazard is #1 in both; after that the lists diverge quickly.

Two illustrative cases:

- **Sergio Agüero:** VAEP #19, xT #109. Why? Agüero is an elite finisher — he scores more from his shots than expected (positive xG over-performance). VAEP rewards this directly because goals appear in the training labels. xT cannot see finishing skill at all because $g_{x,y}$ is league-average shot conversion, not player-specific. The framework structurally cannot distinguish Agüero from any other player who shoots from the same zones.

- **Alexis Sánchez:** xT #7, VAEP #106. The opposite case. Sánchez had a poor goal-scoring season but his key passes per 90 stayed similar. xT picks up the key passes (they move the ball into high-threat zones); VAEP penalises the missing shots and reduced shot quality.

### The pattern

xT favours playmakers (correlation with assists per 90: 0.53 vs 0.33 for VAEP). VAEP favours goal-scorers (correlation with goals per 90: 0.41 vs 0.26 for xT). This is a direct consequence of design choices, not a model "preference":

- xT's $g$ term uses league-average conversion at each zone, so finishing skill cannot show up in xT.
- VAEP's $P_{score}$ trains on actual goals, so finishing skill shows up directly.

Both rankings deviate substantially from goals + assists alone, which is the basic justification for using either model — they capture something the simple counting stats don't.

### Discrepancies are evidence of neither model being "better"

When two models disagree on a player's ranking, the disagreement reflects what each model is designed to measure. VAEP measures total contribution including finishing. xT measures contribution from ball progression only. Agüero ranks high in VAEP and low in xT because he's elite at finishing and average at progression — both rankings are correct measurements of their respective definitions.

To say one is "better" requires an external ground truth (actual win contribution, transfer fee, expert assessment), and no such ground truth exists. The right way to use these models is not to pick the "correct" one but to use the disagreement itself as signal: a player whose VAEP rank exceeds their xT rank is likely a finisher; a player with the reverse pattern is likely a progression-focused creator. The gap between rankings is informative, and this is the conceptual basis for player-vector and archetype-based approaches that have followed in the literature.

### Robustness asymmetry

The most important quantitative finding, and the one that complicates any "VAEP is more sophisticated" framing.

Test: split the season into two random disjoint halves, compute each player's per-90 rating on each half, correlate the two ratings.

- **xT correlation: 0.89.** xT player ratings are highly stable across random splits.
- **VAEP correlation: 0.25.** VAEP ratings vary substantially across splits.

VAEP ratings on the same player can shift dramatically between two random halves of the same season. xT ratings are stable. The paper diagnoses two reasons:

1. **Goals are extreme outliers in VAEP's value distribution.** A goal scores ~1.0; most actions score near 0. A few goals landing in sample 1 vs sample 2 dramatically shifts a player's aggregated VAEP. The paper notes that for defensive players, a difference of three goals can double or halve their ratings.

2. **xT only depends on zonal patterns, which players are highly consistent at.** Players reliably perform similar action types from similar locations across matches; xT picks up this stable pattern. VAEP's contextual sensitivity picks up real signal but also picks up rare-event noise.

A controlled test confirms the diagnosis: restricting VAEP to ball-progressing actions only and to offensive value only raises its split-half correlation to 0.59 — better, but still well below xT's 0.89. So even controlling for actions and risk, VAEP is noisier than xT.

### What the robustness number doesn't tell you

Critical methodological caveat: split-half correlation measures *consistency*, not *validity*. A model that always returns 0.5 has perfect split-half correlation and zero usefulness. xT's high robustness is consistent with capturing something stable about playing style, but it is not evidence that xT captures the *right* thing.

The deeper question — whether VAEP's added variance is signal or noise — cannot be answered from split-half correlation alone. If VAEP is picking up genuine differences between strong and weak performances that xT smooths out, then VAEP's volatility is a feature and xT is regression toward the mean. If VAEP is overfitting to goal-scoring noise, then xT is correctly identifying stable underlying skill. **The paper documents the tradeoff but does not resolve which interpretation is correct.** This remains an open question.

---

## What the paper does not address

Four notable gaps:

1. **No external validation.** Neither model is compared to outcome-relevant ground truth (wage levels, transfer fees, expert ratings, win contributions). The paper compares the two models to each other and to goals/assists.

2. **No analysis of defensive players.** Both models concentrate top-25 lists on attackers. Van Dijk is #81 in VAEP and #142 in xT. The paper notes this but doesn't dig into why or what to do about it.

3. **No feature-importance analysis for VAEP.** The 151-feature CatBoost model is treated as a black box throughout. No ablation of which features drive contextual sensitivity vs noise.

4. **Single league, single season, single data provider.** Generalisation to other leagues, vendors, or seasons is untested.

---

## Practical implications

The paper does not say "use VAEP" or "use xT." It says they're different tools with different operating points on a tradeoff curve. The right choice depends on the use case.

- **xT for evaluating consistent positional/playmaking skill.** Stable across samples. Tells you which players reliably move the ball into threatening areas. Useful for scouting playmakers, identifying build-up patterns, opponent profiling.

- **VAEP for evaluating per-game performance and context-dependent contributions.** Less stable but captures more of what happened in this specific match. Useful for post-match analysis, identifying performances under specific conditions, evaluating risk-adjusted contributions.

- **Neither alone for defenders.** Both models concentrate value on attackers. Defensive evaluation requires extensions or different frameworks.

- **Neither for off-ball contributions.** Tracking-data models required.

"Use both in tandem" is the easy answer; the harder, more useful framing is "use them for different decisions." The disagreement between them is itself signal. A player whose VAEP rank is much higher than their xT rank is plausibly a finisher specialist; the reverse pattern indicates a progression specialist. This is the basis for player-vector and archetype-based approaches that have followed.

### On smoothing VAEP

A natural design question is whether VAEP's robustness can be improved without giving up its contextual sensitivity. The paper's diagnosis (goals as outliers) suggests several interventions:

- **Smooth the target.** Replace binary goal labels with PSxG (post-shot xG) or expected-goal sums in the window. PSxG is strictly denser signal than goals — every shot has a PSxG, but most shots don't become goals. Cost: PSxG only exists where shots occur, so this primarily helps offensive VAEP near shooting events; defensive VAEP improvements are smaller.

- **Regularise the model.** Stronger regularisation of the gradient boosted trees reduces sensitivity to rare events. Cost: loses some contextual sensitivity.

- **Aggregate smarter.** Bayesian shrinkage at the player level pulls ratings toward position priors, reducing the influence of rare high-value events. Cost: introduces hierarchical assumptions.

- **Ensemble VAEP and xT.** Weighted average of the two ratings. Cost: loses interpretability of either component.

Each intervention trades context for stability. There is no free lunch — robustness improvements come at the cost of either model expressiveness, target specificity, or aggregation simplicity. The honest position: VAEP's volatility is partly inherent to its design (fine-grained context comes with fine-grained noise), and the right operating point depends on what you're trying to do with the metric.

---

## Bottom line

xT and VAEP are not competing answers to the same question — they are different operating points on a tradeoff between contextual sensitivity and robustness. xT trades expressiveness for stability and interpretability; VAEP trades stability and interpretability for expressiveness. The paper's empirical comparison documents this tradeoff cleanly without resolving which side is correct, because there is no external ground truth that would resolve it.

The framework $V(a_i) = Q(S_i) - Q(S_{i-1})$ unifies both models and provides a template for evaluating new ones. The location-vs-feature axis and the possession-vs-window axis are orthogonal design choices; xT and VAEP happen to occupy opposite corners (location + possession vs feature + window), but other combinations are in principle possible and have been explored in the broader literature.

The robustness asymmetry is the paper's most important practical finding and the one that most complicates a simple "VAEP is better" story. Use it as a reminder that more sophisticated models trade stability for expressiveness, and that consistency is not validity.