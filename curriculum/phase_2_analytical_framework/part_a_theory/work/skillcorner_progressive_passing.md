# SkillCorner — Progressive Passing: Evaluating Decision-Making (Charles Myers, December 2024)

**Source:** [skillcorner.com/articles/progressive-passing](https://skillcorner.com/articles/progressive-passing). Practitioner-facing article from a tracking-data vendor.

**Genre note:** This is a *product marketing piece with real analytical content*. Practitioner-facing analytics writing is a real and legitimate genre, and SkillCorner does it better than most. But it is not peer-reviewed work, and shouldn't be evaluated as such. Looser empirical standards, claims that exceed evidence, visual examples carrying argumentative weight, commercial subtext — all expected for the genre and present here.

## What's new vs the prior canon

One conceptual move: **opportunity-adjusted tendency**. Raw counts of progressive actions confound *willingness/skill* with *opportunity*. Adjust counts by opportunities to recover the underlying tendency.

Worked example: Jorginho, Rodri, Enzo Fernández rank 80-90th percentile for line-breaking pass counts but play in highly ball-dominant teams that generate many opportunities. Palhinha (Fulham) and Éderson (Atalanta) score around average on raw counts but exceptionally high on tendency — they take a high *proportion* of available opportunities. Same player evaluated very differently depending on adjustment.

This is, in econometric language, a **selection-on-observables correction**: you're trying to evaluate a player's *tendency parameter* (behavioural propensity) net of the *exposure* (opportunity rate). Raw count confounds them; the rate metric separates them under the assumption that opportunity is conditionally independent of latent skill.

The article doesn't use this vocabulary because the author isn't trained in causal inference. The methodological move is causal in spirit regardless.

## Framework on the five design axes

| Axis | SkillCorner Progressive Passing |
|---|---|
| **State** | Tracking + event data; player and ball positions, defensive structure, teammate movement |
| **Target** | Player tendency = (progressive passes attempted / opportunities available) |
| **Horizon** | Per-pass and aggregated per-game |
| **Architecture** | Ratio metric. Numerator: counted passes by type. Denominator: opportunities defined by tracking-derived configuration. |
| **Credit assignment** | Per-passer; off-ball runners credited separately in the product. |

Design-axis change vs OBSO/Brefeld: shift on Target. Earlier models computed *state value* per player. This computes *behavioural tendency* per player relative to environmental context. Different evaluation question.

## What's load-bearing

1. **The denominator definition.** Everything rests on SkillCorner's ability to identify "opportunities" — moments where a progressive pass *could have been* played. The construct definition (what counts as a runner in behind? what counts as a passing line being available?) makes the metric meaningful. **The article does not disclose the operational definitions in writing.** Central methodological vulnerability.

2. **The risk/reward framing.** Article ends with: "the profiles of de Jong, Kimmich & Rodri are perhaps reflective of controlling play rather than actively taking risk." Doing real conceptual work — the metric on its own can't tell you whether high or low tendency is correct; tactical context required.

3. **The combination plot — difficulty × bypass count.** Most informative visualisation in the article. Combines tendency with execution quality.

## What the limitations are

The article does not flag these.

1. **No outcome grounding.** "Line-breaking pass" defined by configuration, not by what happens next. A pass breaking two lines and intercepted at the third counts the same as one releasing a striker for a shot. No P(score) component, no expected possession value. Major regression from OBSO and even from xT on this dimension.

2. **Opportunity definition is the whole game and is not disclosed.** Unknown:
   - How "available" a passing line has to be to count
   - Whether opportunity counting assumes the passer can see the option (no occlusion model mentioned)
   - Whether opportunities are weighted by quality
   - Whether failed-attempt opportunities count toward opportunity *and* attempt
   
   Cannot replicate or critique what's not visible.

3. **No confidence intervals, no statistical tests, no held-out validation.** Tendency metrics on small denominators are extremely noisy. Article doesn't report sample sizes or sample variance.

4. **Risk/reward asymmetry isn't measured.** Article gestures at it. Cost of failed line-breaking passes (turnover in dangerous areas, opposition transition) not quantified anywhere. 80% tendency with 50% completion treated equivalently to 80% tendency with 80% completion.

5. **Selection bias in opportunity attribution.** Some passers *create* their opportunities (carrying ball into position, drawing pressure to open space behind). Others *receive* opportunities passively. Metric attributes opportunity to passer regardless of how they got into the situation. Conflates ball-progression skill with line-breaking skill.

6. **Practitioner-piece pattern: definitions where claims should be.** "Elite teams need players capable of...", "this comes with an element of risk/reward", "perhaps reflective of controlling play rather than actively taking risk." These are *interpretations*, not findings. Academic paper would distinguish them; practitioner article uses them interchangeably.

## Use-case-conditioned dominance — the synthesis position

The two metrics answer different questions; which dominates depends on the user's question.

**When opportunity-adjusted tendency beats counts:**
- Opportunity rate varies sharply across teams/roles (the article's central case)
- Projecting performance to a different team context (high tendency at Fulham → presumably more progressive passes at Arsenal)
- The behavioural disposition itself is the evaluation target (recruitment scouting: "does this player look for line-breaking passes?")

**When counts beat opportunity-adjusted tendency:**
- Opportunity rate is itself a property of the player (DM who creates opportunities by carrying, drawing pressure, advanced positioning has higher counts because of additional skill; opportunity adjustment removes credit for that skill)
- Sample size is small (rate metrics on small denominators have variance that swamps signal)
- Team's tactical instructions correlate with opportunity definition (a manager instructing recycling vs progression makes tendency look poor for compliant players)
- Predicting outcomes that aggregate over actual passes (goals, EPV, team performance) — count metrics are closer to the target

**Calibrated position:** for the recruitment-scouting use case the article addresses, opportunity-adjusted tendency dominates because counts are confounded by team environment in ways that make them poor predictors of how a player will perform in a new environment. For contribution evaluation in the player's current environment, counts are at least as informative and possibly more honest.

The first attempt at this answer overclaimed by stating dominance broadly. The right move is use-case-conditioned dominance.

## What's actually useful for portfolio work

**The opportunity-adjustment principle is real and applies broadly.** For any rate-style metric in football where the rate depends on environmental context (pass count, shot count, defensive action count, recovery count), the adjusted-for-opportunity version is more defensible than the raw version *for propensity evaluation*. The trick: opportunity must be measured consistently. SkillCorner's value proposition is that they've operationalised opportunity via tracking; that's what they're charging for.

**Discipline:** when computing any rate-style metric, ask whether the denominator captures the relevant exposure. If opportunities aren't observable, the rate metric is unstable.

## Audience consideration — rhetorical mode for portfolio distribution

Three modes for analytical writing:

1. **Academic/rigorous (mode 1)** — peer-review-grade, full methods, conservative claims. Slow, less viral, high credibility.
2. **Practitioner/applied (mode 2)** — SkillCorner-style. Visual, definitive-sounding, claims exceed evidence. Fast, readable, lower credibility with academics.
3. **Hybrid (mode 3)** — applied conclusions with academic rigour underneath. Karun Singh's xT post is canonical. Hardest to execute but highest impact.

**Strategic positioning implication:** the target career path requires mode 3, not mode 2. The whole point of bringing causal econometrics into football is producing work the field can't currently produce — work that, by construction, has rigour existing practitioner-content lacks. Showing up with SkillCorner-style writing wastes the wedge.

Mode 2 has a place: strategic distribution pieces that get reach for mode-3 work already published. Karun Singh writes the rigorous xT post and blog summaries; the combination works. But rigorous post comes first.

**Risk to actively manage:** drifting toward mode 2 because engagement is higher there. Engagement is downstream of credibility; mode-2-only doesn't build credibility for the target role.

## Connections going forward

- **Brefeld 2021:** also concerned with measuring player ability against an opportunity baseline, but does it via SG metrics on space quality (continuous-quality version vs SkillCorner's count-rate version).
- **OBSO:** offers the missing outcome grounding. Natural extension: weight each progressive pass opportunity by OBSO of receiver — opportunity-adjusted and outcome-grounded.
- **Ghosting (next paper):** addresses symmetric problem on defensive side — what defenders should do, against which actual behaviour can be evaluated.
- **Pearl's Book of Why:** opportunity adjustment is textbook causal-inference (controlling for exposure to recover treatment effect). The vocabulary should feel natural.

## Logged for OPEN_QUESTIONS.md

1. **Outcome-weighted opportunity-adjusted progressive passing.** Combine SkillCorner's opportunity adjustment with OBSO-style outcome grounding. Each progressive pass opportunity weighted by value of resulting position. Tractable as portfolio question if opportunity definition can be constructed from open data.

2. **Risk-adjusted tendency.** Separate "took the opportunity and completed" from "took the opportunity and failed." Compute completion-conditional tendency vs raw tendency. Test whether risk-adjusted version correlates differently with team outcomes.

3. **Replicate SkillCorner's opportunity counter from open data.** What's the simplest defensible operational definition of "opportunity"? Build it from StatsBomb open data, compare to count-only metrics. Direct critique of SkillCorner's main claim with full methodological transparency. **Strategically interesting:** engages directly with the field's leading data vendor on their own analytical claims. Mode-3 artefact that makes the work legible to people inside clubs.

## Methodological self-assessment from this session

**Improved:**
- Took a real position when invited to dodge. Resisted the safe "use both" answer.
- Eventually identified mode 3 as the right rhetorical target after pushback. The pushback worked because the underlying claim (mode 2 is fine for career acceleration) was defensible-sounding but wrong on inspection.
- Acknowledged the lazy defence rather than digging in. Conceded cleanly.

**Still showing:**
- Strong-words overclaim: "tendency does dominate" without conditioning on use case. Same pattern as Pareto, only, must from prior sessions. Universal-dominance claims rarely survive scrutiny.
- Confused variable framing: discussed scoring probability distributions when the relevant distribution was opportunity rate variance across players. Same flavour as Q2 OBSO conflating Axis A and Axis B.
- Conditions listed (occlusion, opportunity quality, opportunity creation, risk) were defects of the metric, not conditions for when the metric dominates counts. Answered "what's wrong with the metric" instead of the question asked.
- Bundled mode 2 and mode 3 as equivalent options for career acceleration when they're substantively different paths. Bundling-to-defer-decisions pattern.

**Pattern to actively work against:** universal dominance claims. When you take a position, ask: under what conditions does this not hold? If you can't answer, you've overclaimed. Use-case-conditioned positions are stronger than universal ones because they require less defending.

## Grade

1.5/3. Position-taking present. Defence weak; conditions mis-targeted; first condition conceptually muddled. Improvements over earlier sessions on engagement style; recurring patterns at the answer-construction level.

## Cumulative Week 2 spatial models so far

- WOS: 6/9 (67%)
- OBSO: 6.5/9 (72%)  
- Brefeld tight: 1.5/3 (50%)
- SkillCorner tight: 1.5/3 (50%)

Plateau holding. Discipline points showing up consistently at the answer-construction level. Improvements from here are meta-level: catching universal-dominance claims, variable-framing conflations, and condition/defect distinctions before posting. One paper remaining: Ghosting (Le et al. 2017).