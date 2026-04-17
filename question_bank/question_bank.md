# Football Analytics Portfolio Questions

A structured set of 25 questions ordered from foundational to sophisticated. All data confirmed publicly available. Answering 10-12 publicly with clean code and practitioner-readable write-ups makes you competitive. Answering all 25 makes you exceptional.

Start with Question 1.

---

## Data Sources

| Source | What It Contains | Access |
|--------|-----------------|--------|
| **StatsBomb Open Data** | Event-level data — passes, shots, pressures, carries, freeze frames. Multiple competitions including Champions League, La Liga, WSL, Bundesliga | https://github.com/statsbomb/open-data |
| **FBref** | Aggregated player and team stats for Big 5 leagues from 2017-18 onward. xG, xA, progressive passes, pressures, defensive actions | https://fbref.com |
| **Transfermarkt** | Player market valuations, transfer fees, contract data, career histories | https://www.transfermarkt.com |
| **Understat** | Shot-level xG data for Big 5 leagues | https://understat.com |

**Python libraries:** `statsbombpy`, `worldfootballR` (R), `mplsoccer`

---

## Tier 1: Foundational — Event Data Fluency

*Goal: Prove you can work with football event data professionally. Demonstrates tactical vocabulary and data handling competence.*

---

### Question 1
**Who are the most effective pressers in the Champions League, and does pressure success rate predict defensive outcomes?**

**Data:** StatsBomb open data — Champions League event data

---

### Question 2
**How does passing network structure change when a team is winning versus losing?**

**Data:** StatsBomb open data — La Liga (Barcelona seasons)

---

### Question 3
**Which shot locations produce the biggest gap between xG and actual conversion rate, and what does that tell us about shooter quality versus chance quality?**

**Data:** StatsBomb open data + Understat

---

### Question 4
**How does pressing intensity vary by game state, scoreline, and match minute — and do leading teams press less?**

**Data:** StatsBomb open data — multiple competitions

---

### Question 5
**Which players receive the ball most frequently under pressure, and how does their subsequent action quality compare to unpressured receipts?**

**Data:** StatsBomb open data — pressure and ball receipt events

---

### Question 6
**What is the relationship between progressive carrying and chance creation — and which teams rely on it most?**

**Data:** StatsBomb open data + FBref

---

## Tier 2: Intermediate — Recruitment and Player Valuation

*Goal: Prove you can build and communicate player evaluation frameworks. Directly relevant to recruitment analyst roles.*

---

### Question 7
**Which players are most undervalued by xG alone when you add on-ball value to the picture?**

**Data:** StatsBomb open data — OBV calculable from event data

---

### Question 8
**How much does a player's pass completion rate change under pressure versus not under pressure, and which players maintain quality best?**

**Data:** StatsBomb open data — pass pressure flags

---

### Question 9
**Which midfielders in the Big 5 leagues produce the highest progressive pass volume relative to their team's possession share?**

**Data:** FBref — Big 5 leagues 2017-2024

---

### Question 10
**Do players who transition from a high-possession team to a low-possession team show systematic declines in key metrics beyond what team context predicts?**

**Data:** FBref player stats + Transfermarkt transfer records

---

### Question 11
**Which forwards have the largest gap between non-penalty xG and actual goals — consistently across three or more seasons?**

**Data:** FBref + Understat — multi-season

---

### Question 12
**How does a player's defensive contribution as measured by pressures and tackles change when their team's possession share drops significantly?**

**Data:** FBref — player defensive stats across seasons

---

## Tier 3: Intermediate — Tactical and Opposition Analysis

*Goal: Prove you can answer questions a coaching staff or opposition analyst actually asks. Directly relevant to club-side roles.*

---

### Question 13
**How do set piece routines differ between the top and bottom halves of the Premier League table — volume, location, and outcome?**

**Data:** StatsBomb open data — set piece events

---

### Question 14
**Which teams concede the most xG from transitions specifically, and how does that correlate with their pressing intensity in possession?**

**Data:** StatsBomb open data — carry and shot events with play pattern flags

---

### Question 15
**How does crossing frequency and success rate vary by league, and is there a relationship between crossing volume and xG generated?**

**Data:** StatsBomb open data + FBref

---

### Question 16
**Which defensive systems allow the fewest shots from central zones, and how does their pressure positioning differ from high-conceding teams?**

**Data:** StatsBomb open data — shot location and pressure events

---

### Question 17
**How do managers adapt their team's defensive shape in the final 15 minutes when protecting a one-goal lead?**

**Data:** StatsBomb open data — event sequences with minute and game state

---

## Tier 4: Advanced — Causal and Econometric

*Goal: Demonstrate the econometric and causal thinking that differentiates you from every other applicant. This is the layer nobody else in the pool has.*

---

### Question 18
**Does pressing intensity cause improved defensive outcomes, or does team quality confound the relationship?**

**Data:** FBref — PPDA and defensive metrics + Transfermarkt squad values as quality proxy

---

### Question 19
**How much of a player's possession value metrics are attributable to the individual versus the system — using player transfers as natural experiments?**

**Data:** FBref player stats 2017-2024 + Transfermarkt transfer records

---

### Question 20
**Are managers systematically late with substitutions relative to optimal timing — and can injury-forced substitutions serve as an instrument to test this?**

**Data:** StatsBomb open data — substitution and injury events + FBref match outcomes

---

### Question 21
**Does a causally-adjusted player valuation model predict transfer fees better than raw output metrics — and where does the market systematically misprice players?**

**Data:** FBref + Transfermarkt transfer fees + Understat xG

---

### Question 22
**Which tactical decisions show the largest gap between observed frequency and game-theoretically optimal frequency — using opponent response patterns as evidence?**

**Data:** StatsBomb open data — multi-season event sequences across competitions

---

## Tier 5: Advanced — System-Level

*Goal: Demonstrate the ability to sustain a complex, multi-source analytical project end to end. These are conference-submission quality questions.*

---

### Question 23
**Can you build a pressing system quality metric that separates tactical design from personnel quality across Big 5 leagues?**

**Data:** FBref PPDA and pressing metrics + Transfermarkt squad values + StatsBomb open data

---

### Question 24
**How does team xG performance in the first versus second half correlate with substitution patterns — and do teams that substitute earlier outperform their first-half xG trajectory?**

**Data:** StatsBomb open data — shot and substitution events with minute stamps

---

### Question 25
**Which leagues show the greatest systematic difference between xG and actual goals at the team level over multiple seasons — and what structural factors explain it?**

**Data:** Understat — all Big 5 leagues multi-season + FBref

---

## Sequencing Guidance

| Questions | What It Proves | Target Role |
|-----------|---------------|-------------|
| 1-6 | Event data fluency, tactical vocabulary | Any entry-level analytics role |
| 7-12 | Recruitment methodology, player evaluation | Recruitment analyst |
| 13-17 | Tactical and opposition analysis | Club-side analyst |
| 18-22 | Causal inference, econometric thinking | Senior analyst, data company |
| 23-25 | End-to-end system-level analysis | Conference submission, senior roles |

**Minimum viable portfolio:** Answer 10-12 questions publicly with clean code on GitHub and practitioner-readable write-ups.

**Target:** Answer all 25.

**Start here:** Question 1. It is the most accessible entry point into the StatsBomb event data schema and directly connects to the tactical vocabulary being built in Phase 1 of the study plan.