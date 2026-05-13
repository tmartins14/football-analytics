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
