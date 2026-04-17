# Phase 2: Analytical Frameworks
**Duration:** 6 weeks | **Time commitment:** 1 hour/day (~7 hours/week)
**Prerequisite:** Phase 1 complete, at least one candidate problem identified

**Goal:** Understand the existing analytical landscape well enough to 
identify where your candidate problem fits, what data exists to investigate 
it, and where current frameworks fall short

---

## What This Phase Is

Phase 2 has two distinct parts. Part A builds theoretical fluency — you will 
read the core analytics literature critically, not to summarize it but to 
evaluate it. Part B builds practical fluency — you will get your hands on 
real football data and learn to work with it in Python.

The critical lens for every piece of reading in Part A:
1. What problem was this framework built to solve?
2. What does it deliberately ignore or assume away?
3. When would using it lead you to the wrong conclusion?

---

## Part A — Theory (Weeks 1–3)

### Week 1: Expected Goals (xG)

**Core question:** xG measures shot quality based on historical conversion 
rates. When is that useful and when does it mislead you?

#### Reading Material
| Article | Purpose |
|---|---|
| StatsBomb: xG explained | Foundational mechanics |
| Edd Webster: xG deep dive | Critical evaluation |
| StatsBomb: Post-shot xG | How PSxG differs from xG and why |

**Key distinction to understand:**
- xG = shot quality (location, assist type, situation)
- PSxG = shot quality after ball leaves foot (accounts for placement)
- Conversion rate above expectation = finishing skill proxy

**Reaction prompt:** When would a manager be misled by xG? Build a specific 
scenario.

---

### Week 2: Possession Value & Pressure Metrics

**Core question:** How do analysts measure the value of actions that don't 
directly create shots?

#### Reading Material
| Article | Purpose |
|---|---|
| StatsBomb: VAEP explained | Valuing every action |
| StatsBomb: Pressure events | How pressure is defined and measured |
| Friends of Tracking: Possession value | Framework overview |
| PPDA literature | Measuring press intensity |

**Key concepts:**
- VAEP (Valuing Actions by Estimating Probabilities)
- Possession value chains
- PPDA as press intensity proxy — and its limitations
- Pressure success rate vs pressure frequency

**Reaction prompt:** PPDA tells you how often a team presses. What doesn't 
it tell you? When would two teams with identical PPDA scores be playing 
completely different styles?

---

### Week 3: Defensive Metrics & Shape

**Core question:** Why is defensive contribution the hardest thing to 
measure in football analytics?

#### Reading Material
| Article | Purpose |
|---|---|
| StatsBomb: Defensive actions | What events data captures defensively |
| SkillCorner: Defensive shape metrics | Block depth, line height, compactness |
| Any literature on PPDA limitations | Where press metrics break down |

**Key concepts:**
- Defensive line height
- Block depth classification (high/mid/low)
- Compactness metrics
- Why preventing shots is harder to measure than creating them

**Reaction prompt:** If you were a Sporting Director trying to evaluate 
whether a manager's defensive system is working, which metric would you 
trust most and why? Which would you distrust?

---

## Part B — Practice (Weeks 4–6)

### Week 4: Data Sources & Environment Setup

#### Data Sources to Know
| Source | Access | What It Contains |
|---|---|---|
| FBref | Free | Match stats, advanced metrics, historical data |
| StatsBomb Open Data | Free (GitHub) | Full event data for select competitions |
| Understat | Free | xG data for top European leagues |
| Capology | Free | Wage bill estimates |
| SkillCorner | Paid | Tracking data, shape metrics |
| Wyscout / Opta | Paid (club access) | Professional-grade event data |

#### Environment Setup
```python
# Required libraries
pip install pandas numpy matplotlib seaborn mplsoccer statsbombpy requests
```

#### Exercise 1: FBref Scrape
Pull defensive stats for all Premier League teams this season from FBref.
- Extract: PPDA, pressures, defensive line height proxies
- Output: clean pandas DataFrame
- Deliverable: `01-data-sources-exploration.ipynb`

---

### Week 5: Working With Event Data

#### Exercise 2: StatsBomb Open Data — xG Analysis
Using StatsBomb's free dataset:
- Load a full match of event data
- Calculate xG by shot location
- Visualize shot maps using mplsoccer
- Compare xG vs actual goals for a team across a season
- Deliverable: `02-xg-analysis.ipynb`

#### Exercise 3: Pressing Metrics
Using StatsBomb pressure events:
- Calculate PPDA for a set of teams
- Identify pressing triggers from event sequences
- Compare high-press vs low-block teams on pressure metrics
- Deliverable: `03-pressing-metrics.ipynb`

---

### Week 6: Connecting Data to Your Candidate Problem

This week is not prescriptive. Take your strongest candidate problem from 
Phase 1 and do a preliminary data investigation.

**Questions to answer:**
- What data would I need to investigate this properly?
- Is that data freely available or behind a paywall?
- What does a preliminary cut of the data suggest?
- Is the problem still interesting or has the data killed it?

**Deliverable:** `04-candidate-problem-exploration.ipynb`

This notebook is the bridge to Phase 3. It should end with either a refined 
research question or a documented reason why you moved to a different 
candidate problem.

---

## What Success Looks Like

By the end of this phase you should be able to:
- Explain what xG, PPDA, VAEP, and PSxG measure and when not to use them
- Pull and clean football data from at least two free sources in Python
- Produce a basic shot map and pressing metrics visualization
- Have run a preliminary data investigation on your candidate problem
- Articulate clearly what data you would need to answer your research 
question properly

---

## Key Vocabulary Built This Phase
- xG / PSxG / xGA
- VAEP
- PPDA
- Possession value
- Event data vs tracking data
- Pressure events
- Expected threat (xT)
- Goals above expectation