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

- **`libs/statsbomb/`** — the Python data layer: extracts StatsBomb open
  data into the JSON the visualizations consume.

- **`libs/footballd3/`** — a custom D3 component library for the
  visualizations (shot maps, pass networks, formations, and more).

- **`apps/`** — consumers of the libraries above that are their own
  runnable/deployable unit, rather than library code or analysis.
  Currently empty.

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

