# AUDIT v3 — Part 0 Data Audit

Status: complete, pending Tyler's review
Scope: [DATA-SPEC-v3.md](./DATA-SPEC-v3.md) Part 0, read-only investigation only — no code changes
Match in scope: `3943043` (Spain vs England, Euro 2024 Final)

Answers the eight questions in DATA-SPEC-v3's "Part 0 — Data audit" section.
Evidence is drawn from: (a) this repo's committed derived-extract JSON under
`data/euro-2024/3943043/`, which is real per-event data for this match
reshaped by the existing extractors; (b) this repo's own code
(`libs/statsbomb/`, `scripts/`); (c) the vendored `statsbombpy` package's own
schema documentation and an independent StatsBomb parser (`mplsoccer`), for
schema-level questions a live API call would otherwise answer. No network
calls were made during this audit (read-only investigation, per the spec);
anywhere that limitation leaves a question only schema-confirmed rather than
confirmed against this match's actual raw events is called out explicitly
below, not glossed over.

## 1. Do 3943043's events contain `obv_*` fields? Which event types carry them?

**No. Absent categorically, not just unused.**

- `data/README.md` states directly (lines 37-39): *"StatsBomb OBV (On-Ball
  Value) is a paid product and is not available in the open data tier.
  Analyses that would otherwise use OBV need to either substitute
  open-source alternatives (xT, VAEP) or be scoped down."*
- The vendored `statsbombpy` package's own README
  (`.venv/lib/python3.12/site-packages/statsbombpy-1.19.0.dist-info/METADATA`)
  shows a plain `sb.events(match_id=303299)` column listing (lines ~396-470)
  with **no** `obv_*` columns at all. The `obv_against_after`,
  `obv_for_net`, `obv_total_net`, etc. columns (lines 1297-1303) appear only
  in the example for `sb.events(..., include_360_metrics=True)`, directly
  under: *"The open data does not include the 360 metrics. This is
  currently only available to customers with a data subscription."*
- `grep -rni "obv" libs/ ai/ data/` finds zero references anywhere in this
  codebase — no extractor reads or writes an `obv_` field.

**Answer for Part 3 (Decision 6):** no OBV cross-check is possible for this
match's open data. The fallback already named in the spec ("use xT, our own
approximation") is the only option, not an alternative.

## 2. Do events carry a `counterpress` flag? On which types? (tier 2)

**Present in the schema; not independently confirmed non-null for this
match's actual events.**

- `counterpress` is a plain, non-paid open-data boolean column — it appears
  in `statsbombpy`'s base `sb.events()` schema example (METADATA line 408),
  not gated behind `include_360_metrics`.
- `mplsoccer/soccer/statsbomb.py:516`, an independent StatsBomb parser,
  treats it as a generic top-level boolean alongside `under_pressure`:
  `for col in ['counterpress', 'under_pressure', 'off_camera', 'out']: ...`
  — i.e. it is not restricted to a specific event type, the same way
  `under_pressure` isn't.
- No extractor in `libs/statsbomb/` currently reads `counterpress`
  (`grep -rni "counterpress" libs/ ai/` finds nothing), and no committed
  derived JSON for 3943043 surfaces it. Confirming its true/false
  distribution for this specific match would need a live `sb.events()`
  call, which this read-only audit did not make.

**Open item, not resolved here:** whether `counterpress` is actually
populated (and on which event types) for 3943043 specifically needs a
one-off raw-events read before tier 2's transition questions (Q11) can rely
on it.

## 3. Are raw events (and 360) for all 51 Euro 2024 matches available locally? If not, how does the existing pipeline fetch them?

**Not all 51, and nothing is persisted raw anywhere on disk.**

- `data/euro-2024/` has **44 of 51** match-id subdirectories (36 group + 8
  R16 + 4 QF + 2 SF + 1 final = 51 total; 7 have no directory at all).
  Of the 44: 43 have `match_stats.json` (the extractor's "done" marker);
  `data/euro-2024/3930167/` exists but is **completely empty**
  (extraction attempted or scaffolded, never completed). Only **37 of 44**
  have `freeze_frames_goals.json` (6 "complete" matches —
  3930172, 3930173, 3930181, 3930182, 3938645, 3941019 — lack it).
- Only match **3943043** has the full extractor suite (`heatmap_buckets/`,
  `player_events/`, `progressive_map_*.json`, `possession_60.json`,
  `cumulative_xg.json`, `possession_shares_3943043.json` — 19M total vs.
  e.g. `3930163/`, which has none of those). `scripts/extract_euro2024.py`'s
  12-step batch loop (shots, xt, momentum, goal_animation, match_stats,
  substitutes, pass_network, formation, team_shape, freeze_frames,
  convex_hull, tactical_findings) never calls `extract_heatmap`,
  `extract_progressive_map`, `extract_possession`, or
  `extract_cumulative_xg`/possession_shares — those extra files for
  3943043 were run one-off outside the batch script.
- **No raw/cache directory with persisted StatsBomb JSON exists.**
  `data/raw/statsbomb/` and `data/processed/statsbomb/` are both gitignored
  per `docs/ARCHITECTURE.md` *and* present-but-empty on this machine.
- **Fetch mechanism: live network, not a local clone.** `libs/statsbomb/`
  extractors import `from statsbombpy import sb` and call `sb.events()`,
  `sb.matches()`, `sb.frames()`, etc. The installed `statsbombpy` (1.19.0)
  hardcodes its data source in `statsbombpy/config.py`:
  ```python
  OPEN_DATA_PATHS = {
      "events": "https://raw.githubusercontent.com/statsbomb/open-data/master/data/events/{match_id}.json",
      "frames": "https://raw.githubusercontent.com/statsbomb/open-data/master/data/three-sixty/{match_id}.json",
      ...
  }
  ```
  and caches responses only in an **ephemeral** per-process sqlite file in a
  fresh temp dir (`install_cache(mkdtemp(), backend="sqlite",
  expire_after=600)` — 10 minutes). Every cold run re-fetches from GitHub's
  public open-data repo over the network.
- `scripts/extract_euro2024.py` is **not** hardcoded to 3943043: it loops
  over `sb.matches(competition_id=55, season_id=282)` (Euro 2024) with an
  optional `--match-id` flag to restrict to one, and is idempotent
  (`if not force and (out_dir / "match_stats.json").exists(): skip`) — which
  explains the partial 44/51 state: it has been run, just not completed for
  every match.
- **360 data genuinely exists for most (not all) Euro 2024 matches**,
  confirmed empirically (37/44 local dirs have a non-trivial
  `freeze_frames_goals.json`), matching `data/README.md`'s "360 data is only
  included for selected competitions" caveat — Euro 2024 is one of them, but
  this isn't guaranteed for an arbitrary competition. `load_360_frames()` in
  `libs/statsbomb/utils.py` tries `sb.frames()` first and falls back to a
  direct `requests.get()` against the same GitHub raw JSON URL on a known
  `statsbombpy` bug for some Euro 2024 match ids. No raw, full per-match 360
  stream (only the derived goals-only extract) is persisted locally
  anywhere.

**Answer for seam rule 9 / Part 2:** reading the other 50 matches is
possible, but only over the network each time, and today only 44/51 are
even extracted to derived JSON locally (one of those an empty stub) — Part
2's reference-data build will need either live fetches for all 51 or the 7
missing (plus the one empty) matches backfilled first.

## 4. Does `progressive_map` exist, and what is its exact definition?

**Yes — `libs/statsbomb/extract_progressive_map.py`.**

- `PROGRESSIVE_THRESHOLD: float = 0.25` (line 61) — StatsBomb's own
  25%-of-remaining-distance-to-goal-centre threshold (module docstring,
  line 6). `GOAL_CENTER_X = 120.0`, `GOAL_CENTER_Y = 40.0` (lines 57-58).
- Distance helper (lines 64-74):
  ```python
  def _dist_to_goal(x: float, y: float) -> float:
      return math.sqrt((GOAL_CENTER_X - x) ** 2 + (GOAL_CENTER_Y - y) ** 2)
  ```
- Core rule (lines 77-101):
  ```python
  def _is_progressive(x0, y0, x1, y1, threshold=PROGRESSIVE_THRESHOLD) -> bool:
      """Progressive = end-point distance to goal <= (1 - threshold) * start-point distance to goal."""
      d_start = _dist_to_goal(x0, y0)
      if d_start == 0:
          return False
      return _dist_to_goal(x1, y1) <= (1.0 - threshold) * d_start
  ```
- Applies to completed **and** incomplete open-play passes, and to carries
  (always "completed" per StatsBomb convention). Set pieces are excluded via
  `play_pattern` against `SET_PIECE_PLAY_PATTERNS` (`libs/statsbomb/utils.py:30-36`).
- Already reused (imported, not reimplemented) by
  `libs/statsbomb/extract_player_events.py:83` for its own
  `is_progressive`/`distance_gained` fields — single source of truth today.
- Committed output for this match: `data/euro-2024/3943043/progressive_map_england.json`,
  `progressive_map_spain.json`.

**Conflict with v3's draft — flagged, not resolved:** DATA-SPEC-v3.md §"Tier
1 definitions" Q3 (line 109) says "Reuse `progressive_map`'s definition if
one exists. If not: [fallback]" and the fallback it drafts (`x ≥ 48` start
restriction, end ≥10 yards closer to goal centre **or** ends in the box) is
materially different from the existing extractor's rule above (no zone
restriction, no box-entry OR-clause, a relative 25%-closer-to-goal test
instead of a flat 10-yard one). Per the spec's own text this should resolve
to using `extract_progressive_map`'s existing definition outright — Tyler to
confirm the drafted fallback is dropped, not layered on top of it.

## 5. Exact outcome values used for successful Tackle, Interception and Ball Recovery in this data

Pulled from `data/euro-2024/3943043/player_events/*.json` (built by
`libs/statsbomb/extract_player_events.py`, which preserves StatsBomb's raw
`duel_outcome`/`interception_outcome`/`ball_recovery_recovery_failure`
strings verbatim — see `_event_outcome`, lines 96-130).

- **Tackle** (`Duel`, `duel_type == "Tackle"`) — distinct outcomes across
  this match's 35 Tackle duels: `Success In Play` (10), `Won` (10),
  `Lost Out` (9), `Lost In Play` (6). **There is no single clean "success"
  value** — both `"Won"` and `"Success In Play"` are successful tackles.
  Examples:
  ```json
  // outcome = "Won" (Kobbie Mainoo, min 24)
  {"type":"Duel","duel_type":"Tackle","outcome":"Won","under_pressure":true, ...}
  // outcome = "Success In Play" (Lamine Yamal, min 5)
  {"type":"Duel","duel_type":"Tackle","outcome":"Success In Play","under_pressure":true, ...}
  ```
- **Interception** (`interception_outcome`) — distinct values present in this
  match: `Won`, `Success In Play` (both successful), `Lost In Play`
  (failure; no `Lost Out`/`Success Out` seen here). Example:
  ```json
  // outcome = "Won" (Daniel Olmo, min 22)
  {"type":"Interception","outcome":"Won", ...}
  ```
- **Ball Recovery** — **no outcome field at all.** Mere event presence is
  the success signal; the only flag is `ball_recovery_recovery_failure`,
  mapped by the extractor to `outcome: "Failure"`. Example:
  ```json
  // data/euro-2024/3943043/player_events/6765.json
  {"type":"Ball Recovery","outcome":"Failure","minute":40,"second":48, ...}
  ```
  Non-failure recoveries simply have `outcome: null`.

**Landmine found along the way, not asked for but relevant to any
"successful duel" aggregate:** every `Duel` of `duel_type == "Aerial Lost"`
in this match (33 of them) has `outcome: null`, and there is **no**
`"Aerial Won"` `duel_type` anywhere in the data — StatsBomb appears to log
only the *losing* side of an aerial duel as a `Duel` event; the winning
side's touch is captured elsewhere (e.g. a Clearance or Pass with its own
aerial-won flag), not as a second Duel event.

**Conflict with v3 — flagged, not resolved:** Q5's `win_zone` and
`defensive_action_height` (DATA-SPEC-v3.md lines 128-130) both say
"successful Duel (Tackle)" without naming which outcome values count. Given
the two non-overlapping success values above, Tyler should confirm both
`"Won"` and `"Success In Play"` are intended as "successful" before Part 1
builds against it.

## 6. Presence of `pass.cross`, `pass.cut_back`, through-ball technique, `pass.shot_assist`, `pass.goal_assist`, `under_pressure`

**All six are real, standard open-data fields — confirmed at the schema
level for all; confirmed present and non-null in this match's actual data
for three of them.**

- Schema-level: the vendored `statsbombpy` README's events-column table
  (METADATA, non-360-gated, lines 396-470) lists `pass_cross`,
  `pass_cut_back`, `pass_goal_assist`, `pass_shot_assist`, `pass_technique`,
  and `pass_through_ball` all as standard (not paid) open-data columns —
  `pass.cut_back` in particular is a real StatsBomb field name, not a guess.
  `mplsoccer/soccer/statsbomb.py:633-635` independently confirms the
  Through Ball mechanism is current (`pass_through_ball` is the older,
  being-phased-out boolean; `pass.technique.name == "Through Ball"` is the
  current value StatsBomb is moving to).
- **`pass.shot_assist` / `pass.goal_assist` — confirmed present and non-null
  in this match's committed derived data**, via `extract_player_events.py`'s
  `_key_pass()` (lines 200-221):
  ```json
  // data/euro-2024/3943043/player_events/39461.json (Cole Palmer, min 89)
  {"type":"Pass","key_pass":true,"assisted_shot_xg":0.057442, ...}
  // data/euro-2024/3943043/player_events/316046.json (Lamine Yamal, min 54)
  {"type":"Pass","key_pass":true,"assisted_shot_xg":0.243106, ...}
  ```
- **`under_pressure` — confirmed present and populated across 12 credited
  event types** in this match (aggregated across all `player_events/*.json`):
  ```
  Ball Recovery True=12/False=51   Carry True=240/False=465   Clearance True=42/False=0
  Dispossessed True=21/False=0     Dribble True=25/False=0    Duel True=68/False=0
  Interception True=0/False=5      Miscontrol True=8/False=7  Pass True=156/False=677
  Pressure True=0/False=327        Shot True=8/False=17       Block True=0/False=41
  ```
  Example: `data/euro-2024/3943043/player_events/16532.json` (Daniel Olmo,
  min 65:22): `{"type":"Pass","under_pressure":true,"outcome":null,...}`.
- **`pass.cross`, `pass.cut_back`, Through Ball technique — schema-confirmed
  only, not yet confirmed non-null specifically for 3943043.** No extractor
  in this repo currently reads `pass_cross`, `pass_cut_back`, or
  `pass_technique` (`grep -rni "cut_back\|pass_cross\|pass_technique" libs/`
  finds zero hits outside `DATA-SPEC-v3.md` itself), so there's no committed
  artifact with a concrete true/false example from this match for these
  three. Confirming them would need a one-off raw-events read (or Part 1's
  new `extract_chance_creation.py`, which needs them anyway).

## 7. Where minutes played per player can be read from

**Not a stored field anywhere today — computable from two existing files.**

- No dedicated minutes-per-player extractor exists
  (`grep -rn "minutes_played" libs/ ai/ docs/` only turns up the open
  question in `DATA-SPEC-v3.md:252` itself). No `lineups.json` is cached
  under `data/euro-2024/3943043/` either — `sb.lineups(match_id=...)` is
  called live and never persisted (`libs/statsbomb/utils.py:138-158`
  `build_nickname_lookup`, `libs/statsbomb/extract_substitutes.py:81`
  `get_eligible_players`).
- The two pieces needed are both already committed:
  1. **`data/euro-2024/3943043/substitutes.json`** (written by
     `libs/statsbomb/extract_substitutes.py`) gives `on_minute`/
     `on_second`/`on_period`/`replaced_player` per substitute, e.g.:
     ```json
     {"player_id": 39461, "display_name": "Cole Palmer", "on_minute": 69,
      "on_second": 53, "on_period": 2, "replaced_player": "Kobbie Mainoo"}
     ```
     For a starter subbed off, the *incoming* player's `on_minute` is the
     outgoing starter's final minute (`replaced_player` names them).
  2. **`libs/statsbomb/extract_formation.py:186-187`** already computes the
     match-end minute from events: `match_end = int(events["minute"].max())`.
- Minutes played = `(match_end_minute, or the replacing sub's `on_minute` if
  subbed off) − (0, or own `on_minute` if a substitute)`. Nothing currently
  does this arithmetic or writes a `minutes_played` field anywhere — it
  would be new code in Part 3, built from these two existing sources.

## 8. Whether `socceraction` installs and loads local StatsBomb JSON without network access

**Not installed, not declared as a dependency at all — currently
unverifiable either way.**

```
$ find .venv -iname "*socceraction*"      # no output
$ grep -i socceraction uv.lock             # no output
```

`pyproject.toml`'s full dependency list has nothing socceraction-related:

```toml
dependencies = [
    "statsbombpy>=1.14.0", "pandas>=2.0", "numpy>=1.26", "matplotlib>=3.8",
    "mplsoccer>=1.4", "scipy>=1.12", "jupyter>=1.0", "anthropic>=1.0.0",
    "python-dotenv>=1.2.3", "pydantic>=2.13.4",
]
[dependency-groups]
dev = ["interrogate>=1.7.0", "nbstripout>=0.7", "pytest>=8.0"]
```

Per this task's read-only/no-network constraint, the package was not
installed to test it. Upstream, PyPI `socceraction`'s
`socceraction.data.statsbomb` module is documented to provide a
`StatsBombLoader(getter="local", root=...)` class for reading a local JSON
tree directly — distinct from the network-backed `statsbombpy`/API path —
but this is **unverified against this project**, since there is no installed
copy here to inspect.

**Conflict with v3 — flagged, not resolved:** `socceraction` is central to
the entire Player Contribution method (Decisions 6/7, the xT grid in Part
3), but isn't installed anywhere in this project today. Adding it is a real
dependency change (`pyproject.toml` + `uv sync`) that v3 doesn't currently
call out as a Part 0/1 prerequisite — Tyler to confirm before Part 1 starts
building against it.

## Summary of open questions for Tyler

Per the spec's own "Stop. Tyler updates this spec's decisions from the
audit" — these are stated as findings, not resolved here:

1. **Q3's progressive-action definition** (item 4 above): `progressive_map`
   already exists with a different rule than v3's drafted fallback. Confirm
   the existing extractor's definition is used outright.
2. **Reference-data feasibility** (item 3): only 44/51 Euro 2024 matches are
   extracted locally (one of those empty), and nothing is cached raw —
   Part 2 needs either live fetches for every match or a backfill pass first.
3. **`socceraction` isn't installed** (item 8): needs to be added as a
   dependency before Part 3 (or any audit follow-up) can verify its local-
   JSON loading claim.
4. **Q5's "successful Duel (Tackle)"** (item 5): the data has two
   non-overlapping success values (`"Won"`, `"Success In Play"`) — confirm
   both count.
