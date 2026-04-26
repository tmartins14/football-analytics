# Expected Goals: Literature Review Summary

A consolidated summary of the xG literature review conducted before the discussion pivoted to portfolio strategy. Sources are primary papers and the broader peer-reviewed and grey literature around them, anchored in part on Edd Webster's `football_analytics` repo as a reference.

A note on Webster's repo: it is a curated catalogue of links, not a literature review in itself. What follows draws on the primary sources Webster catalogues plus the broader academic and grey literature.

---

## 1. Pre-history (1968-2012)

The conceptual ancestor of xG predates the term by decades.

- **Vic Barnett and Sarah Hilditch (1993)** used the phrase "expected goals" in a paper on artificial pitch surfaces in English football.
- **Charles Reep** (notational analysis, 1950s onward) is the unacknowledged grandfather of every shot-quality model — counted shots and goals from positions. Pollard & Reep (1997) is the modern citation.
- **Alan Ryder (2004)** transplanted the methodology from ice hockey. His "shot quality" paper laid out the entire template — collect data, analyze goal probability conditional on shot circumstances, build a model — and explicitly noted the analytic methods were classics from statistics and actuarial science.
- **Brian Macdonald (2012)** formalized the term "expected goals" in his MIT Sloan paper for the NHL, validating with mean squared error and 10-fold cross-validation.

Football borrowed this wholesale. Early adopters were bloggers operating outside academia — Sander IJtsma, Sam Green, Michael Caley, 11tegen11, StatsBomb's Ted Knutson — which is why the foundational "literature" is disproportionately blogs and conference proceedings rather than journal articles.

**Strategic observation:** the field's foundational metric came in via cross-domain transfer (hockey → football), with an actuarial framing. The field is receptive to methodological imports from quantitative disciplines, but has historically borrowed from non-causal statistical traditions. The opening for causal econometrics is real precisely because it hasn't been done.

---

## 2. The foundational era (2012-2018)

Event-data logistic regression. This is the era that defined "xG" as the public knows it.

### Key papers

**Lucey et al. (2014/2015)** — "Quality vs Quantity: Improved shot prediction in soccer using strategic features from spatiotemporal data," MIT Sloan. The most-cited single paper. Used data from an anonymous 20-team league with almost 10,000 shots and examined spatiotemporal patterns within a ten-second window before each shot, finding match context lowered the model's average error from 0.1745 to 0.1662. First serious attempt to push beyond shot-location features into possession-context features. Methodologically vulnerable in ways now well-documented (endogeneity in build-up features).

**Caley (2013-2015)** — "Shot Matrix" series on Cartilage Free Captain, then SB Nation. Not peer-reviewed but historically important. Documented the marginal contribution of each shot feature (distance, angle, body part, assist type, fast break, etc.) using full-season EPL data. Where most of the public's intuition about "what goes into xG" actually came from.

**Eggels, Van Elk & Pechenizkiy (2016)** — Eindhoven thesis work using random forests; AUC ROC of 0.823. Among the first to systematically benchmark non-linear models against logistic regression for xG.

**Rathke (2017)** — *International Journal of Sports Science and Coaching*. Old-school: split the pitch into eight zones and analyzed goal probability from shots in each. Useful as baseline benchmark, methodologically primitive (essentially a lookup table).

**Spearman (2018)** — "Beyond Expected Goals," MIT Sloan. Pivotal paper. Used event data from a 14-team professional league during 2017/18 and a probabilistic approach to quantify "off-ball scoring opportunities" (OBSO). Conceptual leap: instead of "what's the probability this shot becomes a goal?" he asked "what's the probability a goal is scored from this position, regardless of whether a shot is taken?" This is the bridge from xG to pitch-control / EPV / VAEP frameworks. The title itself argues the shot-conditional formulation is a dead-end.

**Brechot & Flepp (2020)** — *Journal of Sports Economics*. Found that a shot from a free kick is more likely to be a goal, from a penalty kick even more so, and from a header significantly less so, vs. an open-play shot. They are economists; framed xG explicitly as a residual-extraction tool ("luck vs skill").

### The standard feature set that crystallized

Distance, angle, body part (foot/head/other), shot type/situation (open play, set piece, counter), assist type. Logistic regression was the dominant algorithm; gradient boosting became standard later.

---

## 3. The positional / tracking-data era (2019-2022)

Once tracking data became available to researchers, the obvious limitation of event-only models — that they couldn't see defenders or the goalkeeper — got addressed.

### Key papers

**Anzer & Bauer (2021)** — "A Goal Scoring Probability Model for Shots Based on Synchronized Positional and Event Data in Football," *Frontiers in Sports and Active Living*. Depending on how you count, the first peer-reviewed positional-data xG paper. They explicitly note that no peer-reviewed publication had previously introduced a positional data-driven xG model. Key argument: the positioning of the defensive team, especially the goalkeeper, has a crucial influence on shot outcome. Reported AUC ROC of 0.814. Also applied SHAP to xG models, demonstrating that shot distance is the most influential factor.

**Decroos & Davis (2019/2020)** — "Interpretable prediction of goals in soccer," AAAI workshop. Important for the philosophy: black-box models don't help coaches.

**Robberechts & Davis (2020)** — A useful survey of xG to that point. The Davis/KU Leuven group is one of two or three nodes (the others being StatsBomb research and the Anzer/Bauer/DFB axis) producing serious peer-reviewed soccer ML.

**Bransen & Davis (2021)** — "Women's football analyzed: interpretable expected goals models for women," IJCAI. Critical paper: formalized that men's xG models systematically misprice women's shots because of differences in shot profiles, goalkeeper positioning, and finishing rates. Stats Perform now deploys separate xGOT models for men's and women's football.

---

## 4. Post-shot xG (xGOT / PSxG)

A parallel branch for evaluating goalkeepers and finishing execution rather than chance creation.

The conceptual split: **xG is a pre-shot model; xGOT is a post-shot model.** Expected Goals on Target is built on historical on-target shots and includes the original xG plus the goalmouth location where the shot ended up. Stats Perform's enhanced 2024-2025 version accounts for execution qualifiers — deflections, mishits, swerve.

**De-la-Cruz-Torres et al. (2025)** — *MDPI Big Data and Cognitive Computing*. Built an xGOT model using the 2022 World Cup with goalkeeper-position geometric features. AUC-ROC of 0.67, 85% accuracy. The mediocre AUC is honest reporting of how hard the post-shot problem is.

**Goalkeeper subliterature:** xGOT-conceded vs goals-conceded is the standard metric for goalkeeper shot-stopping; "Goals Prevented" is its public-facing name. Known limitations: ignores sweeping, distribution, command of the box. Provider-specific calibration differences make cross-source comparison unreliable.

---

## 5. Interpretability and explainability (2021-2024)

A consistent thread of complaint: practitioners don't trust black boxes.

**Van Haaren (2021)** — "Why would I trust your numbers? On the explainability of expected values in soccer," arXiv 2105.13778. The title is the thesis.

**SHAP-based explainability** has become standard. Anzer & Bauer (2021) and Davis et al. (2024) consistently identify shot distance as the dominant feature, with angle, defensive pressure, and body part as secondary.

**Bayesian mixed models** — A 2024 *Frontiers in Sports and Active Living* paper on interpretable xG using Bayesian mixed models. Motivation: hierarchical structure (shots within players within teams within leagues). Standard ML throws this away.

**Sumpter (2025)** — "Wordalisation" of xG models using LLMs. Builds an xG model using logistic regression, uses regression coefficients to write sentences describing how factors contribute, then uses LLMs to give engaging description. The fact that Sumpter (a founder of the field) is working on translating xG outputs into natural language tells you where the unsolved problems sit.

---

## 6. The critical turn (2024-2026)

The most important section. The literature's most recent serious work is *not* about better xG models — it's about exposing what xG can't do.

### Key papers

**Davis, Robberechts & Bransen (2024)** — "Biases in Expected Goals Models Confound Finishing Ability," arXiv 2401.09940. The most damaging recent critique. Three hypotheses tested:

1. The deviation between actual and expected goals is an inadequate metric due to high variance and limited sample sizes.
2. Including all shots in cumulative xG calculation may be inappropriate.
3. xG models contain biases arising from interdependencies in the data that affect skill measurement.

Findings: sustained overperformance of cumulative xG requires both high shot volumes and exceptional finishing; including all shot types can obscure the finishing ability of proficient strikers; **there is a persistent bias that makes the actual-vs-expected gap closer for excellent finishers than it really is.**

The kicker: the model is contaminated by the labels. Good finishers' shots train the model, so the model partly absorbs their skill into the baseline. Classic econometric problem — endogeneity and selection bias — not seriously addressed in operational xG models.

**Counterfactual xG (Xu et al., 2025)** — "What If They Took the Shot? A Hierarchical Bayesian Framework for Counterfactual Expected Goals," arXiv 2511.23072. Standard xG models treat all players as statistically equivalent shooters. This "average player" assumption overlooks substantial variation in individual finishing ability. The counterfactual framing is Pearl's vocabulary; the move from "what's the average shot's probability?" to "what would *this player's* probability be on this shot?" is the move from associational to causal xG.

**Entropy-Adjusted xG (Lamberts, 2026)** — Recent grey literature. Decomposes a player's xG into a "core" repeatable component and a context-dependent component using shot dispersion across location, type, and probability. Implicit claim: cumulative xG without entropy adjustment is a bad predictor of forward-looking finishing.

**Mead, O'Hare & McMenemy (2023)** — *PLOS ONE*. Used FIFA ratings as a proxy for player ability; produced a Brier score of 0.0799 and AUC ROC of 0.8. Methodologically interesting: explicitly tested whether including a player-quality covariate improves xG. It does. **This should worry you** — if FIFA ratings (subjective scout ratings) improve a chance-quality model, the chance-quality model isn't really measuring chance quality alone; it's measuring chance quality conditional on the average shooter.

**Skills vs Luck decomposition** — Random-effects meta-analysis applied to deviations from xG across European leagues. Mainstream econometric methodology finally being applied to football. Results consistently show single-season xG-deviation is dominated by luck for most teams and players.

---

## 7. Where the literature converges (consensus)

Settled claims:

1. **Distance and angle dominate.** Shot distance is the most important feature across nearly every published model, often by a wide margin.
2. **Body part matters.** Headers convert at substantially lower rates than feet from comparable positions.
3. **Game state matters.** Penalties have to be modeled separately or excluded; most published models do one or the other.
4. **Positional/tracking data improves performance over event-only data, but marginally.** AUC gains from event-only to event+tracking are typically 0.01-0.03. The big jump is *not* in raw model performance — it's in the new questions you can ask.
5. **Different providers produce non-comparable xG values for the same shot.** Operationally critical, rarely emphasized in popular discourse.
6. **Logistic regression is competitive with gradient boosting on event-only data.** XGBoost/LightGBM win in raw AUC by small margins; the cost is interpretability. Most production club models still use logistic regression.

---

## 8. Where the literature has unresolved fights

These are the dissertation-tier opportunities:

1. **Player finishing ability — does it exist as a stable, identifiable trait?** Davis et al. 2024: barely, for most players, and the standard methodology biases against detecting it. Counterfactual xG (Xu et al. 2025) and entropy-adjusted approaches (Lamberts 2026) are early fixes. **No one has used a serious causal identification strategy here.** Closest is hierarchical Bayesian shrinkage, which is associational.

2. **Defensive contribution to shot suppression.** xG-against works at team level but is largely useless for individual defenders, because event data doesn't capture what defenders prevent. Fundamental selection-on-observables problem.

3. **Cross-league calibration.** Models trained on EPL transfer poorly to Eredivisie or MLS. The literature has no clean way to disentangle "league strength" from "shot-distribution differences" from "model misspecification."

4. **The endogeneity of build-up features.** When Lucey et al. include "ten seconds before the shot" features, those features are partially caused by the same offensive process that produced the shot. Conditioning on them confounds the estimate of pure chance quality.

5. **Goalkeeper-specific finishing models.** xGOT exists, but goalkeeper *positioning decisions* are themselves a function of the shooter's prior actions. Causal goalkeeper evaluation is wide open.

---

## 9. Honest assessment of the field

**Mature in one narrow sense:** shot-conditional probability prediction with event or tracking features is a solved engineering problem. Nobody is going to win an analytics job by training a slightly better XGBoost on the same features everyone else uses.

**Genuinely immature in the senses that matter:**

- Causal identification of finishing skill is unresolved; the most cited recent paper (Davis et al. 2024) is essentially a confession of this.
- Endogeneity issues in build-up-aware xG models are not addressed in the published literature.
- Counterfactual reasoning has only just begun to enter the methodology (Xu et al. 2025).
- The communication problem — why coaches don't trust the numbers — is being worked on by Sumpter himself with LLMs, indicating the people inside the field believe the problem isn't solved.

---

## 10. What this implies for portfolio work

Three operational implications drawn from the lit review:

1. **Don't build another xG model.** Solved-problem theatre. Use StatsBomb's shipped `statsbomb_xg` field. Build custom xG only for a specific framing reason (cross-league calibration audit, finishing-bias replication, etc.).

2. **The Davis et al. 2024 finishing-bias paper is the single most important recent piece** for portfolio work. Translating it into operational implications for practitioners — "here's what this means for how a club like ours should use xG-overperformance numbers" — is exactly the translation gap that exists between research and practice.

3. **The endogeneity and causal-identification gaps in the literature are real, but addressing them seriously requires research-paper-tier work.** That's not the right vehicle here. The right vehicle is *applying* the insights from the critical 2024-2026 literature to operational decisions, not advancing the methodological frontier.