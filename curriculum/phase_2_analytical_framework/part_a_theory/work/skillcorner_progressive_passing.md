# Space and Control in Soccer (Martens, Dick, Brefeld 2021)

**Source:** Frontiers in Sports and Active Living, July 2021. [Open access PDF](https://www.frontiersin.org/journals/sports-and-active-living/articles/10.3389/fspor.2021.676179/full).

**Citation note:** Conventionally referenced as "Brefeld et al. 2021" but Martens is first author. Brefeld is senior author and the data-driven motion model approach builds on his earlier work (Brefeld, Lasek, Mair 2019).

## What's new vs the prior canon

One change, executed cleanly. Replace WOS's parametric Gaussian player-influence with a data-driven KDE built from each player's historical trajectories. Bin trajectories by initial velocity (standing/walking/jogging/running/sprinting), kernel-density-estimate the reachable endpoints per bin per player. Each player gets their own movement model. Everything downstream — pitch control, pitch value, space quality — keeps WOS's structure.

Pitch value side is unchanged. Still defender-position-as-revealed-value, still feed-forward neural net trained on defender clustering, still goal-distance normalisation. Same circularity issues as WOS for defensive evaluation.

## Framework on the five design axes

| Axis | Brefeld 2021 |
|---|---|
| **State** | 22-player + ball spatial configuration; positions and velocities; tracking data |
| **Target** | Same as WOS — pitch control, pitch value, space quality |
| **Horizon** | Time-to-arrive determined by ball travel; pitch value still trained on instantaneous defender configurations |
| **Architecture** | Same shape as WOS, different motion model. Player influence becomes data-driven KDE instead of parametric Gaussian. PC and pitch value remain. Pitch value still uses FFNN trained on defender positioning. |
| **Credit assignment** | Per-player space quality, summed and aggregated to per-player SG metrics |

## What's load-bearing

1. **The KDE motion model is the actual contribution.** Per-player, empirical, captures individual movement characteristics (max speed, acceleration, agility) that WOS averages out via its uniform parametric Gaussian.

2. **Empirical validation against external metrics.** First paper in the spatial-models lineage with meaningful quantitative validation:
   - PC at pass destination correlates with possession outcome (75% positive PC for shot-ending possessions vs noise from baseline)
   - $SG_{rec}$ correlates with non-penalty xG per 90 at $r = 0.66$, $p < 1e\text{-}13$
   - $SG_{pas}$ correlates with xA per 90 at $r = 0.21$, $p = 0.03$
   - $SG_{total}$ correlates with player market value (~6.5% market value increase per 10% SG increase, controlling for team)

3. **The SG redefinition.** "Space generation" in this paper is **not** WOS's SGG.
   - WOS's SGG = dragger metric (relational credit assignment via geometric conditions on defender movement)
   - Brefeld's SG = receiver/passer metric (how much space quality you create as a passer or pass receiver)
   - Different objects with confusingly similar names. Don't conflate in writing or interviews.

## What the limitations are

1. **Pitch value circularity is inherited, not addressed.** Better motion model doesn't fix defender-trained value. The cover shadow / offside step-up critiques from WOS Q3 still apply.
2. **Validation has shared-feature contamination.** $SG_{rec}$ vs xG correlation is partly inflated because both metrics depend on location features. The paper doesn't decompose "real off-ball value identification" from "shared dependency on pitch location."
3. **The 75% positive-PC validation has minor leakage.** Configurations at shot-taking moments approximately have positive PC by construction. Better than baseline; absolute number less impressive than it sounds.
4. **Bundesliga 2017/18 only.** 54 matches. Per-player movement models are empirical to that league/season. Generalisation untested.
5. **Cold-start problem not flagged.** New signings, young players, returners, players in unfamiliar positions are undermodelled. Per-player density estimation requires per-player trajectory volume.

## Empirical-validation methodology

Brefeld's validation approach is the cleanest in the spatial-models lineage to date:

- Correlate against an external, established metric (xG-style) on out-of-sample data
- Report Pearson with confidence interval and p-value, not just point estimate
- Use linear regression with team fixed effects when comparing players across teams (controls for environmental differences)
- Acknowledge shared-feature contamination explicitly when metric and validation metric depend on overlapping inputs

Higher empirical bar than WOS or OBSO; still below econometric peer-review standard.

## Synthesis: defensible-for-this-paper, problematic-for-the-lineage

For *this paper*: Defensible. Holding pitch value constant is the right methodological choice for a clean comparison demonstrating the motion-model swap. Changing two things at once would muddy the contribution.

For the *cumulative spatial-models lineage*: WOS, Brefeld, and most subsequent work all use defender-revealed pitch value. OBSO is the lone exception with outcome-grounded value. Keeping defender-revealed value across the lineage forecloses three things:

1. **Non-circular defensive evaluation.** Can't evaluate defender positioning quality with a model trained on defender positioning. Structural blind spot.
2. **Tactical heterogeneity surfacing.** High-press and low-block teams have meaningfully different value surfaces; revealed-value approach partially blurs this by averaging across league behaviour.
3. **Outcome accountability.** Revealed value is a behavioural proxy; outcome-grounded value is what we actually care about. The lineage avoids the harder modelling problem by anchoring on the easier (and circular) signal.

What the field would look different like: more honest tools, less convenient ones. Context-dependent value harder to communicate but more accurate. This is a trade-off the field has not been willing to make. Audience considerations matter — outcome-grounded value (OBSO-style) is more communicable to non-technical staff because the reasoning chain matches football intuition; revealed-value requires explaining that defender clustering is a *training signal* for value, two abstraction layers from football reasoning.

## Connections going forward

- **SkillCorner progressive passing (next reading):** trajectory-based valuation — where players start when pass is made vs where receiver is when pass is received. Different from value-component fix; addresses the dynamic-context problem from a different angle.
- **Ghosting (Le et al. 2017):** counterfactual defender positioning — closest existing work to addressing defender-revealed circularity in spirit, though through a different mechanism (predict where defenders *should* be rather than infer value from where they *are*).
- **Pearl's Book of Why:** continues to be the conceptual anchor for the causal critique applied here. Defender-revealed value is a textbook case of conditioning on the wrong variable when you want to evaluate that variable.

## Logged for OPEN_QUESTIONS.md

1. **Bayesian outcome-grounded pitch value.** Use defender clustering as informative prior, observed possession outcomes as likelihood, train a posterior pitch value surface that combines both signals. Not in the literature. Candidate research direction; not near-term portfolio item.
2. **Cold-start handling for per-player movement models.** When does Brefeld's KDE approach degrade meaningfully for low-trajectory-count players, and what's the right hierarchical model to share information across similar players? Tractable as portfolio question with sufficient tracking data.
3. **Cross-league transferability of empirical motion models.** Does a Bundesliga-trained Brefeld model produce reasonable PC values on Premier League or La Liga data? Direct test of generalisation. Tractable with multi-league tracking access.