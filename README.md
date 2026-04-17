# Football Analyst University

A self-directed curriculum for aspiring football analysts. Built in public, 
designed to be completed by anyone.

My goal is simple: build a rigorous path from zero tactical knowledge to 
original, defensible analytical research. By the end of this curriculum you 
will be able to:

- Speak the tactical vocabulary practitioners use
- Know when to use — and when not to use — the core analytical frameworks
- Conduct and publish your own original research

I am working through this myself. The notebooks, reactions, and research in 
this repo are my own outputs as I go. You can follow the curriculum 
independently, compare your work to mine, or skip ahead to whatever phase 
is relevant to you.

Football analytics is growing. This curriculum grows with it. 
**Contributions welcome.**

---

## Who This Is For

- Aspiring analysts trying to break into football
- Data professionals from other industries making the transition
- Football fans who want to understand what the numbers actually mean
- Anyone who wants a structured path rather than scattered YouTube videos 
and blog posts

**Prerequisites:** Basic Python. Curiosity about football. Everything else 
is built from scratch.

---

## Repository Structure

```
football-analyst-university/
│
├── .gitignore
├── OPEN_QUESTIONS.md                    # Living log of analytical problems worth investigating
├── README.md
│
├── curriculum/
│   ├── phase_1_tactical_vocabulary/
│   │   ├── SYLLABUS.md
│   │   ├── notes.md
│   │   └── work/
│   │       ├── week_1_reactions.md
│   │       ├── week_2_reactions.md
│   │       ├── week_3_reactions.md
│   │       └── week_4_reactions.md
│   │
│   ├── phase_2_analytical_framework/
│   │   ├── SYLLABUS.md
│   │   ├── part_a_theory/
│   │   │   └── work/
│   │   │       ├── metric_evaluations.md
│   │   │       └── reading_reactions.md
│   │   └── part_b_practice/
│   │       └── notebooks/
│   │           ├── 01_data_sources_exploration.ipynb
│   │           ├── 02_xg_analysis.ipynb
│   │           ├── 03_pressing_metrics.ipynb
│   │           └── 04_defensive_shape_analysis.ipynb
│   │
│   └── phase_3_research/
│       ├── SYLLABUS.md
│       └── work/
│           ├── methodology.md
│           └── research_questions.md
│
├── data/
│   └── README.md                        # Data sources, access instructions, gitignore policy
│
└── question_bank/
    ├── question_bank.md                 # Full question index with tiers and sequencing guidance
    └── questions/
        ├── q01_pressing_effectiveness.ipynb
        ├── q02_passing_network_structure.ipynb
        ├── q03_xg_vs_conversion_rate.ipynb
        ├── q04_pressing_intensity_game_state.ipynb
        ├── q05_press_resistance.ipynb
        ├── q06_progressive_carrying.ipynb
        ├── q07_undervalued_players_obv.ipynb
        ├── q08_pass_completion_under_pressure.ipynb
        ├── q09_progressive_pass_volume.ipynb
        ├── q10_team_transition_player_metrics.ipynb
        ├── q11_consistent_xg_overperformers.ipynb
        ├── q12_defensive_contribution_possession_shift.ipynb
        ├── q13_set_piece_analysis.ipynb
        ├── q14_xg_from_transitions.ipynb
        ├── q15_crossing_analysis.ipynb
        ├── q16_defensive_systems_central_shots.ipynb
        ├── q17_late_game_defensive_shape.ipynb
        ├── q18_pressing_causation.ipynb
        ├── q19_individual_vs_system.ipynb
        ├── q20_substitution_timing.ipynb
        ├── q21_causally_adjusted_valuation.ipynb
        ├── q22_game_theoretic_decisions.ipynb
        ├── q23_pressing_system_quality_metric.ipynb
        ├── q24_substitution_xg_trajectory.ipynb
        └── q25_league_xg_structural_differences.ipynb
```

### Phase 1: The Vocabulary Foundation
*4 weeks — Tactical vocabulary and match analysis*

Build enough tactical vocabulary to watch football analytically and read 
practitioner literature critically. Covers defensive structure, pressing 
systems, attacking shape, and build-up play.

→ [Phase 1 Syllabus](curriculum/phase_1_vocabulary_foundation/SYLLABUS.md)

---

### Phase 2: Analytical Frameworks
*6 weeks — Theory and practice*

Understand the core metrics — xG, PPDA, OBV, VAEP — well enough to know 
when to use them and when they mislead you. Get hands on real football data 
in Python.

→ [Phase 2 Syllabus](curriculum/phase_2_analytical_frameworks/SYLLABUS.md)

---

### Phase 3: Self-Directed Research
*Open-ended — Original analytical work*

Produce one piece of original, defensible research on a football problem 
that practitioners would find credible. This is the phase that differentiates 
you from everyone else who studied the same material.

→ [Phase 3 Syllabus](curriculum/phase_3_self_directed_research/SYLLABUS.md)

---

## Question Bank

25 analytical questions ordered from foundational to conference-submission 
quality. All use publicly available data. Each question has a structured 
notebook — framing, hints, empty code cells, and interpretation prompts. 
No solutions provided.

Answering 10-12 publicly with clean code and practitioner-readable 
write-ups makes you competitive.  
Answering all 25 makes you exceptional.

→ [Question Bank](question_bank/QUESTION_BANK.md)  
→ [Notebooks](curriculum/phase_2_analytical_frameworks/part_b_practice/notebooks/)

---

## Data

All analyses use publicly available data. No proprietary data required.

Primary sources: StatsBomb Open Data, FBref, Transfermarkt, Understat.

→ [Data README](data/README.md)

---

## Contributing

Found an error? Have a better question? Want to add a notebook for a 
question that isn't covered?

Open a pull request or raise an issue. The only requirement is that 
contributions meet the same standard as the existing material: 
defensible methodology, honest limitations, no solutions handed to the 
reader.

---

## About

Built by Tyler — a data engineer with a love for the game. 

This repo is the public record of that journey.