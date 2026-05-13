#!/usr/bin/env bash
set -euo pipefail

# ------------------------------------------------------------
# Football Analytics repo restructure
# Run from repo root. Stages changes but does not commit.
# ------------------------------------------------------------

# --- Safety checks ---------------------------------------------------

if [[ ! -f "OPEN_QUESTIONS.md" ]]; then
  echo "ERROR: OPEN_QUESTIONS.md not found. Are you in the repo root?"
  exit 1
fi

if [[ -n "$(git status --porcelain)" ]]; then
  echo "ERROR: Working tree is not clean. Commit or stash changes first."
  git status --short
  exit 1
fi

echo "Pre-flight checks passed. Starting restructure..."

# --- Create new top-level directories --------------------------------

mkdir -p literature_notes/tactics
mkdir -p literature_notes/action_valuation
mkdir -p literature_notes/spatial_and_off_ball
mkdir -p analyses
mkdir -p match_reactions
mkdir -p research/ideas
mkdir -p scratch/notebooks
mkdir -p football_analytics

# --- Move Phase 1 tactical notes -------------------------------------

git mv curriculum/phase_1_tactical_vocabulary/work/attacking_structure_and_buildup_play.md \
       literature_notes/tactics/attacking_structure_and_buildup_play.md

git mv curriculum/phase_1_tactical_vocabulary/work/defensive_structure_and_pressing.md \
       literature_notes/tactics/defensive_structure_and_pressing.md

# --- Move Phase 2 action valuation notes -----------------------------

git mv curriculum/phase_2_analytical_framework/part_a_theory/action_valuation_models/epv.md \
       literature_notes/action_valuation/epv.md

git mv curriculum/phase_2_analytical_framework/part_a_theory/action_valuation_models/possession_value_review.md \
       literature_notes/action_valuation/possession_value_review.md

git mv curriculum/phase_2_analytical_framework/part_a_theory/action_valuation_models/vaep.md \
       literature_notes/action_valuation/vaep.md

git mv curriculum/phase_2_analytical_framework/part_a_theory/action_valuation_models/xg_lit_review.md \
       literature_notes/action_valuation/xg_lit_review.md

git mv curriculum/phase_2_analytical_framework/part_a_theory/action_valuation_models/xg_psxg.md \
       literature_notes/action_valuation/xg_psxg.md

git mv curriculum/phase_2_analytical_framework/part_a_theory/action_valuation_models/xt.md \
       literature_notes/action_valuation/xt.md

git mv curriculum/phase_2_analytical_framework/part_a_theory/action_valuation_models/xt_v_vaep_comp.md \
       literature_notes/action_valuation/xt_v_vaep_comp.md

# --- Move Phase 2 spatial / off-ball notes ---------------------------

git mv curriculum/phase_2_analytical_framework/part_a_theory/spatial_and_off_ball_models/brefeld.md \
       literature_notes/spatial_and_off_ball/brefeld.md

git mv curriculum/phase_2_analytical_framework/part_a_theory/spatial_and_off_ball_models/ghosting.md \
       literature_notes/spatial_and_off_ball/ghosting.md

git mv curriculum/phase_2_analytical_framework/part_a_theory/spatial_and_off_ball_models/obso.md \
       literature_notes/spatial_and_off_ball/obso.md

git mv curriculum/phase_2_analytical_framework/part_a_theory/spatial_and_off_ball_models/skillcorner_progressive_passing.md \
       literature_notes/spatial_and_off_ball/skillcorner_progressive_passing.md

git mv curriculum/phase_2_analytical_framework/part_a_theory/spatial_and_off_ball_models/wide_open_spaces.md \
       literature_notes/spatial_and_off_ball/wide_open_spaces.md

# --- Move Phase 2 practice notebooks to scratch ----------------------

git mv curriculum/phase_2_analytical_framework/part_b_practice/notebooks/01_data_sources_exploration.ipynb \
       scratch/notebooks/01_data_sources_exploration.ipynb

git mv curriculum/phase_2_analytical_framework/part_b_practice/notebooks/02_xg_analysis.ipynb \
       scratch/notebooks/02_xg_analysis.ipynb

git mv curriculum/phase_2_analytical_framework/part_b_practice/notebooks/03_pressing_metrics.ipynb \
       scratch/notebooks/03_pressing_metrics.ipynb

git mv curriculum/phase_2_analytical_framework/part_b_practice/notebooks/04_defensive_shape_analysis.ipynb \
       scratch/notebooks/04_defensive_shape_analysis.ipynb

# --- Move research and methodology files -----------------------------

git mv curriculum/phase_3_research/work/methodology.md research/methodology.md
git mv curriculum/phase_3_research/work/research_questions.md research/research_questions.md
git mv project_ideas/defensive_decision_quality.md research/ideas/defensive_decision_quality.md
git mv OPEN_QUESTIONS.md research/open_questions.md

# --- Question bank → analyses ---------------------------------------

git mv question_bank/question_bank.md analyses/index.md

# Move each question notebook into its own directory
for nb in question_bank/questions/q*.ipynb; do
  fname=$(basename "$nb" .ipynb)
  mkdir -p "analyses/$fname"
  git mv "$nb" "analyses/$fname/notebook.ipynb"
  # Create empty writeup stub
  cat > "analyses/$fname/writeup.md" <<EOF
# ${fname}

*Writeup pending. The shipped artifact for this analysis lives here.*

## Question

## Approach

## Findings

## Interpretation
EOF
  git add "analyses/$fname/writeup.md"
done

# --- Remove now-empty old directories --------------------------------

# Remove syllabi (deliberately discarded as part of dropping curriculum framing)
# Comment these out if you want to keep them
git rm curriculum/phase_1_tactical_vocabulary/SYLLABUS.md
git rm curriculum/phase_2_analytical_framework/SYLLABUS.md
git rm curriculum/phase_3_research/SYLLABUS.md

# Clean up empty directories
rmdir -p curriculum/phase_1_tactical_vocabulary/work 2>/dev/null || true
rmdir -p curriculum/phase_2_analytical_framework/part_a_theory/action_valuation_models 2>/dev/null || true
rmdir -p curriculum/phase_2_analytical_framework/part_a_theory/spatial_and_off_ball_models 2>/dev/null || true
rmdir -p curriculum/phase_2_analytical_framework/part_a_theory 2>/dev/null || true
rmdir -p curriculum/phase_2_analytical_framework/part_b_practice/notebooks 2>/dev/null || true
rmdir -p curriculum/phase_2_analytical_framework/part_b_practice 2>/dev/null || true
rmdir -p curriculum/phase_2_analytical_framework 2>/dev/null || true
rmdir -p curriculum/phase_3_research/work 2>/dev/null || true
rmdir -p curriculum/phase_3_research 2>/dev/null || true
rmdir -p curriculum/phase_1_tactical_vocabulary 2>/dev/null || true
rmdir curriculum 2>/dev/null || true
rmdir question_bank/questions 2>/dev/null || true
rmdir question_bank 2>/dev/null || true
rmdir project_ideas 2>/dev/null || true

# --- Write new infrastructure files ----------------------------------

# .python-version
cat > .python-version <<'EOF'
3.12
EOF

# .gitignore (overwrites existing — review the diff)
cat > .gitignore <<'EOF'
# Python
__pycache__/
*.py[cod]
*$py.class
.venv/
venv/
env/

# Jupyter
.ipynb_checkpoints/
*.ipynb_checkpoints

# Data — local only
data/raw/
data/processed/

# uv
.uv/

# OS
.DS_Store
Thumbs.db

# IDE
.vscode/
.idea/
*.swp
*.swo

# Output
*.log
.cache/
EOF

# LICENSE
cat > LICENSE <<'EOF'
MIT License

Copyright (c) 2026 Tyler Martins

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
EOF

# pyproject.toml
cat > pyproject.toml <<'EOF'
[project]
name = "football-analytics"
version = "0.1.0"
description = "Football analytics work — literature notes, analyses, and research."
readme = "README.md"
requires-python = ">=3.12"
dependencies = [
    "statsbombpy>=1.14.0",
    "pandas>=2.0",
    "numpy>=1.26",
    "matplotlib>=3.8",
    "mplsoccer>=1.4",
    "jupyter>=1.0",
]

[dependency-groups]
dev = [
    "nbstripout>=0.7",
]

[tool.uv]
default-groups = ["dev"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["football_analytics"]
EOF

# CONTRIBUTING.md
cat > CONTRIBUTING.md <<'EOF'
# Contributing

This repo is primarily my own working portfolio, but contributions that
improve it are welcome.

## What's welcome

- **Issues**: corrections, suggestions for new analytical questions,
  pointers to literature I've missed.
- **Pull requests**: typo fixes, clarifications to existing notes,
  additions to the directory READMEs.

## What's not

- Solutions to the analyses in `analyses/`. The notebooks are deliberately
  left without solutions.

## Code style

- Notebook outputs should be cleared before committing. `nbstripout` is
  configured in this repo to handle this automatically.
- Python: standard PEP 8.
EOF

# README.md (overwrites existing — review the diff)
cat > README.md <<'EOF'
# Football Analytics

Self-directed work in football analytics: literature notes, analytical
questions, match reactions, and original research.

Written and maintained by Tyler Martins, data engineer based in Ontario.

## What's here

- **`literature_notes/`** — notes on the football analytics literature.
  Covers tactical concepts, action-valuation models (xG, xT, VAEP, EPV,
  possession value), and spatial / off-ball models (OBSO, Brefeld,
  Wide Open Spaces, ghosting, SkillCorner progressive passing).

- **`analyses/`** — 25 sequenced analytical questions worked in Python,
  ranging from foundational event-data fluency to system-level research
  problems. Each question is a notebook plus a written interpretation.

- **`match_reactions/`** — tactical reactions from watching matches,
  organized chronologically.

- **`research/`** — open research questions, methodology notes, and
  early-stage research ideas.

- **`football_analytics/`** — a small Python package with shared utilities
  (data loaders, pitch plotting).

- **`data/`** — documentation of data sources used in this repo. Raw and
  processed data are not committed; see `data/README.md` for retrieval
  instructions.

## Setup

This project uses [uv](https://docs.astral.sh/uv/) for environment and
dependency management.

```bash
# Install uv (macOS/Linux)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone and set up
git clone https://github.com/tmartins14/football-analytics.git
cd football-analytics
uv sync

# Run a notebook
uv run jupyter lab
```

## A note on the analyses

The notebooks contain framing, hints, and interpretation prompts.
Solutions are not provided — the analytical work is left to the reader.
This is a working portfolio, not a tutorial.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT. See [LICENSE](LICENSE).
EOF

# data/README.md (overwrites existing — review the diff)
cat > data/README.md <<'EOF'
# Data Sources

This repo does not commit raw or processed data — both directories are
gitignored. This document explains where each dataset comes from, how to
access it, and any constraints to be aware of.

## StatsBomb Open Data

The primary data source for most analyses in this repo.

- **Repo**: https://github.com/statsbomb/open-data
- **Python access**: `statsbombpy` (installed as a project dependency)
- **Scope**: selected competitions, including the Premier League 2003/04
  (Arsenal Invincibles), all FIFA World Cup matches from 2018 and 2022,
  Women's Euro 2022, La Liga (Messi-era Barcelona), Champions League
  finals, and more.
- **Licensing**: free for non-commercial use under the StatsBomb Open
  Data User Agreement.

### Usage

```python
from statsbombpy import sb

competitions = sb.competitions()
matches = sb.matches(competition_id=11, season_id=90)  # La Liga 2020/21
events = sb.events(match_id=matches.iloc[0]['match_id'])
```

A wrapper for loading entire competition-seasons in one call is provided
in `football_analytics/loaders.py`.

### What's not in the open data

- StatsBomb 360 data (freeze frames) is only included for selected
  competitions.
- StatsBomb OBV (On-Ball Value) is a paid product and is not available
  in the open data tier. Analyses that would otherwise use OBV need to
  either substitute open-source alternatives (xT, VAEP) or be scoped
  down.

## FBref

In January 2026, FBref's partnership with Opta ended. Advanced stats
(progressive passes, xG, possession-adjusted defensive actions, etc.)
that previously came from the Opta feed are no longer being added or
updated. Basic stats are still available.

### Workaround: Edd Webster's historical FBref repo

- **Repo**: https://github.com/eddwebster/football_analytics
- **Scope**: historical FBref scrapes including the Opta-era advanced
  stats, covering seasons up to the partnership end.
- **Limitation**: no new data after January 2026.

Analyses in this repo that depend on FBref advanced stats either use
this historical data or have been rescoped.

## Understat

- **Site**: https://understat.com
- **Python access**: `understatapi` or `understat` packages
- **Scope**: shot-level xG data for the top five European leagues and the
  RFPL from 2014/15 onward.
- **Rate limiting**: be polite — cache results locally rather than
  re-fetching.

## Transfermarkt

- **Site**: https://www.transfermarkt.com
- **Access**: scraping. Several Python wrappers exist (`transfermarkt-api`,
  `tfmkt`); evaluate per use case.
- **Scope**: transfer fees, market valuations, contract data, squad
  composition.
- **Considerations**: respect rate limits and the site's terms of service.
  Cache aggressively.

## Local directory layout