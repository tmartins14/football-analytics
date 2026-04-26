# Phase 2 — Part A: Theory

**Duration:** 3 weeks | **Time commitment:** ~7 hours/week
**Prerequisite:** Phase 1 complete, at least one candidate problem identified

**Goal:** Build enough theoretical fluency to know what every major football metric measures, what it ignores, and where it methodologically fails. Identify which methodological gaps your econometrics background is positioned to address.

---

## The Critical Lens

Apply to every reading without exception:

1. **What problem was this framework built to solve?** Not the marketing claim. The actual technical problem.
2. **What does it deliberately ignore or assume away?** Every model makes choices. What did this one choose not to model?
3. **When would using it lead you to the wrong conclusion?** Specific scenarios, not generic caveats.

A reading where you cannot answer all three has not been read critically.

---

## Week 1 — Action Valuation Models

**Core question:** What does it mean to assign a "value" to a football action, and what are the competing answers the field has produced?

### Required reading
- Decroos et al. (2019), *Actions Speak Louder Than Goals: Valuing Player Actions in Soccer* — the VAEP paper. Read in full, including the feature engineering.
- Karun Singh, *Introducing Expected Threat (xT)* — original blog post.
- Van Roy, Robberechts, Decroos, Davis (2020), *Valuing On-the-Ball Actions in Soccer: A Critical Comparison of xT and VAEP* — the comparison paper.
- Fernández, Bornn, Cervone (2019), *Decomposing the Immeasurable Sport: A Deep Learning EPV Framework for Soccer* — at least the introduction and conceptual sections.
- StatsBomb's xG and PSxG explainers — short, foundational, read for vocabulary.

### What to extract
- The three competing metaphysical commitments: value lives in shots (xG), in space (xT), or in trajectory (VAEP).
- How each model handles context — and what context each ignores.
- Why none of these is causal, even when the language used to describe them is causal.

### Reaction prompt
Pick one specific player you watch regularly. Predict where xT and VAEP would disagree about their value, and why. Test the prediction on public data if possible.

---

## Week 2 — Spatial and Off-Ball Models

**Core question:** Most of football happens away from the ball. How does the field measure off-ball contribution, and where does the measurement break?

### Required reading
- Fernández, Bornn (2018), *Wide Open Spaces* — pitch control, pitch value, space generation. The foundational tracking-data paper.
- Spearman (2018), *Beyond Expected Goals* — OBSO and the off-ball scoring opportunity framing.
- Brefeld et al. (2021), *Space and Control in Soccer* — extends Fernández/Bornn with data-driven movement models.
- SkillCorner's progressive passing article — adjusting passing metrics for opportunity, which is the bridge from raw counts to decision quality.
- Le et al. (2017), *Data-Driven Ghosting using Deep Imitation Learning* — predicting where defenders should have been.

### What to extract
- The shift from event-based to continuous spatial measurement.
- How "controlling space" is operationalised mathematically and what assumptions get baked in.
- Why off-ball measurement remains descriptive rather than causal even with tracking data.

### Reaction prompt
Pitch control assumes a player's "control" of a point on the pitch is determined by who reaches it first. Construct a scenario where this assumption produces a misleading conclusion about a player's defensive contribution.

---

## Week 3 — Methodological Foundations

**Core question:** Given that all these metrics are noisy, predictive (not causal), and applied to small samples — what can practitioners actually trust, and where is the field's methodology weakest?

### Required reading
- Pearl, *The Book of Why* — chapters 1–4. You're already reading this concurrently. This is the week to integrate it explicitly with what you've read in weeks 1–2.
- Robberechts (2019, StatsBomb), *Valuing the Art of Pressing* — the most explicit attempt to value defensive actions, and a useful target for your "is this actually causal" lens.
- One PPDA critique piece — pick the densest one you can find, read it for what it implicitly assumes about pressing intent vs execution.
- Choose one of the following as your methodological deep-dive:
  - A paper on hierarchical/Bayesian player rating estimation in any sport (basketball is fine, e.g. RAPM or APM literature).
  - A paper on causal inference in observational sports data (any sport).
  - A paper on the credit assignment problem in multi-agent prediction.

### What to extract
- The distinction between a model that predicts well and a model that estimates causally — and where football analytics conflates the two.
- Why year-on-year stability is the right empirical test for whether a metric captures a real player attribute.
- One specific methodological gap that your econometrics background is positioned to address.

### Reaction prompt
Identify one published football analytics result that you believe is methodologically wrong or overclaimed. State precisely what the error is, what the correct claim would be, and what evidence would settle the question.

---

## What Success Looks Like

By the end of Part A you should be able to:
- Explain what xG, xT, VAEP, EPV, OBV, OBSO, pitch control, and pressure events each measure, in one sentence each, and what each ignores.
- Distinguish predictive from causal claims in football analytics literature.
- Identify at least one specific methodological gap in current public work that your background is positioned to address.
- Defend that identified gap as worth working on, with specific reasoning about why it remains unsolved.

The defensible methodological gap is the most important deliverable. Without it, Part A produced literacy but no positioning.