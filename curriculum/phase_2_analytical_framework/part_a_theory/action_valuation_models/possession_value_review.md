# Possession Value & Pressure Metrics — Summary

## The taxonomy

The reading list bundled action-valuation models with pressure descriptors. They are different objects and should be reasoned about separately.

1. **Action-valuation models** — VAEP, xT, OBV, EPV. Probabilistic models that assign value to events.
2. **Pressing/pressure descriptors** — PPDA, pressure events, counterpressing recoveries. Counts and ratios that describe defending behavior.
3. **Possession descriptors** — field tilt, possession share, deep progressions. Territorial control measures.
4. **Spatial/tracking-based models** — pitch control, pitch value, OBSO, OBPV, space generation. Continuous-space models built on tracking data, addressing off-ball value.

## Action-valuation models

**VAEP (Decroos, Bransen, Van Haaren, Davis 2019).** Values each action as the change in scoring probability minus the change in conceding probability. Two gradient-boosted classifiers trained on game states, looking forward 10 actions. Strengths: handles all on-ball action types, accounts for context. Weaknesses: dodges the credit assignment problem (only on-ball actions valued), the 10-action lookahead generates confounders, predictive model misinterpreted as causal estimator, selection on dependent variable in training labels.

**xT (Karun Singh).** Values pitch locations directly. Action value is the difference in xT between start and end location. Encodes the assumption that value lives in space, not in trajectory.

**EPV (Fernández, Bornn, Cervone 2019).** Deep-learning framework that gives expected value over the entire pitch — for every possible pass receiver, drive destination, or shot. The technical infrastructure for measuring decision quality, though not yet used that way at scale.

**xT vs VAEP**: different metaphysical commitments produce different rankings. Van Roy et al. (2020) is the comparison paper.

## Pressure metrics

**PPDA (Passes Per Defensive Action).** Opposition passes in the defending team's final 60% of pitch divided by defensive actions in same zone. A ratio, not a model. What it doesn't tell you: whether the press worked, why it's low (possession dominance is a confounder), pressing structure, triggers, game state effects. Two teams with identical PPDA can have completely different pressing styles — possession-dominant team vs man-marking team, trigger-based vs constant press, mid-block-with-aggressive-ball-near-pressure vs full-pitch press.

**Pressure events (StatsBomb).** Tagged moments where a defender applies pressure on the ball carrier. Better than PPDA because each event is contextual and located.

**Pressure regain rate.** Proportion of pressure events that result in a turnover within 5 seconds. Connects effort to outcome.

The deeper critique of PPDA: it's a ratio of two endogenous quantities (your defending and their passing) over a zone. It measures intent, not execution. Once event data with pressure tags exists, citing PPDA is mostly a tooling/cost decision, not a methodological one.

## Spatial/tracking-based models

**Pitch control (Fernández & Bornn 2018).** Continuous probability that each (x,y) point on the pitch is controlled by a given player/team, based on position, velocity, and distance to ball.

**Pitch value.** The relative value of each pitch location given the ball position. Layered on top of pitch control to identify valuable space.

**Space generation.** Off-ball movement that drags defenders out of position, creating space for teammates. Quantified by Fernández & Bornn using tracking data.

**OBSO (Off-Ball Scoring Opportunity, Spearman et al.).** Probability a player would score if the ball reached them at this moment. Useful near the goal, weak in transition.

**OBPV (Off-Ball Positioning Value, 2024).** Extends OBSO to evaluate space across the entire pitch, including transitions.

**Availability (Brefeld et al.).** Probability that a teammate could receive a pass without interception. Useful for decision-quality analysis because it formalises the "options available" concept.

## What the field is missing

1. **Causal identification.** Almost everything is descriptive. Action values are predictive. "Effect" language is used loosely.
2. **Defensive decision quality.** The Maldini-style positional defending is essentially unmeasured. Offensive decision quality is being chipped at (SkillCorner, EPV); defensive is wide open.
3. **Hierarchical estimation.** Player-level inference from noisy observations should be a partial-pooling problem. The field uses point estimates where posteriors belong.
4. **Off-ball causal effects.** Pitch control and space generation describe what happened. They don't estimate counterfactuals.

## Reliability for practitioners

What practitioners can trust, in tiers:
- **High**: team-level descriptive aggregates over 30+ matches.
- **Medium**: player-level metrics for high-volume actions (striker xG/shot, midfielder pass completion under pressure).
- **Low**: player-level metrics for rare or context-heavy actions (defender VAEP, goalkeeper claims).
- **Very low**: composite single-number player ratings.

Mitigations: triangulation across multiple metrics, trajectory analysis over time rather than level snapshots, formal context adjustments (league, role, team style).