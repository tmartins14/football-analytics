# xG and PSxG — Foundational Vocabulary

**Sources:** Hudl Statsbomb explainers ([What are Expected Goals?](https://www.hudl.com/blog/expected-goals-xg-explained), [Upgrading Expected Goals](https://blogarchive.statsbomb.com/articles/soccer/upgrading-expected-goals/)), FBref [xG Explained](https://fbref.com/en/expected-goals-model-explained/), Statsbomb [Dual Life of Expected Goals](https://blogarchive.statsbomb.com/articles/soccer/the-dual-life-of-expected-goals-part-1/).

---

## Core definitions

**xG (Expected Goals):** probability that a shot becomes a goal, in $[0, 1]$. Computed at the moment of the shot from features describing chance quality.

Standard features: distance to goal, angle, body part, type of preceding action.

Richer features (Statsbomb): goalkeeper position, position of all attackers and defenders, shot impact height, pressure on shooter.

**PSxG (Post-Shot xG):** probability a shot becomes a goal given how it was struck. Uses information available only after the shot: placement, velocity, goalkeeper trajectory. Defined only for on-target shots; off-target = 0.

**Distinction:** xG measures *chance quality*; PSxG measures *shot execution*.

---

## What each is for

| Metric | Primary use |
|---|---|
| xG | Chance creation. Aggregated, predicts future goals better than goals themselves. |
| PSxG | Finishing (offensive) and shot-stopping (defensive, via GSAE = PSxG − goals against). |
| xGA | Defensive chance suppression — xG of shots faced. |
| GSAE | Goalkeeper shot-stopping skill. |
| Goals − xG | Aggregate finishing over- or under-performance. |
| xG chain / buildup | Early extensions of xG to creators (precursors to xT and VAEP). |

---

## What xG/PSxG do not capture

- **No defensive valuation beyond shots.** Shots that didn't happen because of good defending are invisible.
- **No player skill in xG itself.** xG models the average shooter from that situation. Player-level adjustments (Bayes-xG) exist but aren't standard.
- **Model dependence.** Vendors differ. Same shot is 0.25 in one model, 0.35 in another. Statsbomb's is generally considered the highest-quality public model due to freeze-frame data.
- **Designed for aggregates, not single shots.** Single-game xG totals can diverge wildly from goals — that's the metric working as designed, but it limits explanatory use for individual matches.
- **Penalties are static** (~0.76-0.78). Usually reported separately from open-play xG.

---

## How xG fits into the action-valuation lineage

xG is the elemental valuation. Every framework you've covered builds on it:

- **xT** uses crude per-zone shot conversion rates ($g_{x,y}$) — a zonal xG, not a trained model.
- **VAEP's $P_{score}$** is xG generalised over the next 10 actions.
- **EPV's shot component** is an explicit xG model. The shot/goal aspect of EPV is "fundamentally a variant of expected goals models."
- **PSxG** is the natural target replacement for VAEP's binary goal label — denser signal, less streaky.

The whole action-valuation lineage is fundamentally an extension of xG logic from shots to non-shot actions: the question "what's the expected goal value of this action?" generalises "what's the expected goal value of this shot?"