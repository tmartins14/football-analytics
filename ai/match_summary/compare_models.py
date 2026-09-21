"""Model x effort comparison harness for the match summary generator.

SPEC.md Module 2 / Task 2: run five (model, effort) cells on one match — each
cell is one outcome call plus one tactics call — and record what each cost, how
long it took, and what it produced, so the per-section routing decision comes
from measured evidence rather than guesses.

Measurement rules (SPEC "What correct means" #1):
- Token counts come from each response's ``usage`` field, never estimated.
  A call with missing/incomplete ``usage`` is a *failed* call, not a data point.
- Cost is ``usage`` x the RATES table below, applied uniformly to every cell.
- The exact config that produced each output (requested model, model served,
  effort, max_tokens) is recorded next to it.
- No prompt caching, no server-side refusal fallbacks (they would change which
  model answered), no automatic retries: a refusal, ``max_tokens`` stop, or API
  error marks the call failed and the cell is only re-run on explicit request.

Output correctness (outcome grounding, MOTM, tactics grounding) is a manual
read per SPEC — automated scoring is Module 3 — so the ``grading`` block of each
cell starts null and is filled in by hand, then the Markdown is re-rendered with
``--render-only``.

Usage:
    uv run python -m ai.match_summary.compare_models --dry-run
    uv run python -m ai.match_summary.compare_models --confirm-spend [--cells 1,2]
    uv run python -m ai.match_summary.compare_models --render-only
    uv run python -m ai.match_summary.compare_models --export-site PATH

Writes: ai/match_summary/output/3943043/comparison-3943043.json (record) and
        ai/match_summary/output/3943043/comparison-3943043.md (results table).
--export-site writes a slim copy of the record (no raw model outputs) for
tylermartins.com's data/football/ — a manual copy, like the summary JSON itself.
"""

import argparse
import json
import time
from datetime import date
from pathlib import Path
from typing import NamedTuple

import anthropic

from ai.match_summary import generate_match_summary as gen
from statsbomb.utils import fetch_match_info

MATCH_ID = 3943043

# Uniform across cells so no cell is truncated for a config-specific reason;
# thinking tokens count toward max_tokens. Only the tokens actually generated
# are billed, so the ceiling doesn't drive cost.
MAX_TOKENS = 16000

# Standard first-party rates, USD per million tokens — SPEC.md "Rate table",
# as of 2026-09-21. Re-check against live pricing before trusting a new run.
RATES: dict[str, tuple[float, float]] = {
    "claude-haiku-4-5": (1.0, 5.0),
    "claude-sonnet-5": (2.0, 10.0),
    "claude-opus-5": (5.0, 25.0),
}

# Hard stop on cumulative spend (recorded attempts, failed ones included).
SPEND_CEILING_USD = 7.0

# Measured outcome-call input size from the SPEC (tokens) for the full six-file
# payload; the tactics call sends a fixed fraction of it (by character count).
OUTCOME_INPUT_TOKENS = {"claude-haiku-4-5": 124_000}
OUTCOME_INPUT_TOKENS_DEFAULT = 164_000  # Claude 5-family tokenizer

# Rough output-token ranges per cell (both calls, thinking included) used only
# by --dry-run and the ceiling guard; real numbers always come from ``usage``.
OUTPUT_TOKEN_RANGE = {1: (1_200, 1_800), 2: (3_000, 10_000), 3: (3_000, 10_000),
                      4: (2_000, 6_000), 5: (5_000, 25_000)}

OUTPUT_DIR = Path(__file__).parent / "output" / str(MATCH_ID)
RESULTS_JSON = OUTPUT_DIR / f"comparison-{MATCH_ID}.json"
RESULTS_MD = OUTPUT_DIR / f"comparison-{MATCH_ID}.md"


class Cell(NamedTuple):
    """One experiment cell.

    Attributes:
        n (int): Cell number, 1-5, matching the SPEC's table.
        model (str): Model ID to call.
        effort (str | None): ``output_config.effort`` value; None to omit it.
        sweep (str): Which sweep this cell belongs to (documentation only).
    """

    n: int
    model: str
    effort: str | None
    sweep: str


# SPEC.md "Scope — 5 runs on match 3943043". Haiku 4.5 rejects `effort`
# (Models API: capabilities.effort.supported == False), so cell 1 omits it.
CELLS = [
    Cell(1, "claude-haiku-4-5", None, "model"),
    Cell(2, "claude-sonnet-5", "medium", "model + effort"),
    Cell(3, "claude-opus-5", "medium", "model"),
    Cell(4, "claude-sonnet-5", "low", "effort"),
    Cell(5, "claude-sonnet-5", "high", "effort"),
]


def validateUsage(usage: dict | None) -> list[str]:
    """List the reasons a ``usage`` dict can't be trusted for cost accounting.

    Args:
        usage (dict | None): ``response.usage.model_dump()``, or None.

    Returns:
        list[str]: Empty when usage is complete; otherwise one string per problem.
    """
    if usage is None:
        return ["missing usage"]
    problems = [
        f"usage.{key} missing" for key in ("input_tokens", "output_tokens")
        if not isinstance(usage.get(key), int)
    ]
    # Caching is deliberately off; if it happened anyway the flat rates would misprice it.
    for key in ("cache_creation_input_tokens", "cache_read_input_tokens"):
        if usage.get(key):
            problems.append(f"usage.{key} is nonzero (flat rate table would misprice it)")
    return problems


def computeCost(usage: dict, model: str) -> dict:
    """Compute USD cost of one call from its ``usage`` and the rate table.

    Args:
        usage (dict): A complete ``usage`` dict (see validateUsage).
        model (str): Requested model ID, a key of RATES.

    Returns:
        dict: ``{"input_usd", "output_usd", "total_usd"}``, unrounded.

    Raises:
        KeyError: If the model has no entry in RATES.
    """
    rate_in, rate_out = RATES[model]
    input_usd = usage["input_tokens"] * rate_in / 1_000_000
    output_usd = usage["output_tokens"] * rate_out / 1_000_000
    return {"input_usd": input_usd, "output_usd": output_usd, "total_usd": input_usd + output_usd}


def makeCall(section: str, model: str, effort: str | None, response, latency_s: float) -> dict:
    """Turn one raw API response into a recorded call, with its failure reasons.

    Args:
        section (str): "outcome" or "tactics".
        model (str): Requested model ID.
        effort (str | None): Effort sent, or None if omitted.
        response: The raw response from generate_match_summary's ``_request_*``.
        latency_s (float): Wall-clock seconds the request took.

    Returns:
        dict: Config, latency, stop_reason, usage, cost, output, and ``failures``
            (empty when the call is a valid data point).
    """
    usage = response.usage.model_dump() if response.usage is not None else None
    failures = validateUsage(usage)
    if response.stop_reason != "end_turn":
        failures.append(f"stop_reason={response.stop_reason}")

    if section == "outcome":
        parsed = response.parsed_output
        output = parsed.model_dump() if parsed is not None else None
    else:
        text = "".join(b.text for b in response.content if b.type == "text")
        output = text or None
    if output is None:
        failures.append("no output")

    cost = computeCost(usage, model) if not validateUsage(usage) else None
    return {
        "section": section,
        "model_requested": model,
        "model_served": response.model,
        "effort": effort,
        "max_tokens": MAX_TOKENS,
        "stop_reason": response.stop_reason,
        "latency_s": round(latency_s, 2),
        "usage": usage,
        "cost": cost,
        "output": output,
        "failures": failures,
    }


def runCall(section: str, cell: Cell, context: dict, match_label: str, competition: str) -> dict:
    """Make one live API call for a cell and record it (API errors become failed calls).

    Args:
        section (str): "outcome" or "tactics".
        cell (Cell): The cell being run.
        context (dict): Output of load_match_context().
        match_label (str): e.g. "Spain vs England".
        competition (str): e.g. "UEFA Euro 2024".

    Returns:
        dict: A recorded call, see makeCall.
    """
    request = gen._request_outcome if section == "outcome" else gen._request_tactics
    start = time.perf_counter()
    try:
        response = request(context, match_label, competition, cell.model, cell.effort, MAX_TOKENS)
    except anthropic.APIError as err:
        return {
            "section": section, "model_requested": cell.model, "effort": cell.effort,
            "max_tokens": MAX_TOKENS, "latency_s": round(time.perf_counter() - start, 2),
            "usage": None, "cost": None, "output": None,
            "failures": [f"api error: {type(err).__name__}: {err}"],
        }
    return makeCall(section, cell.model, cell.effort, response, time.perf_counter() - start)


def summarizeCell(cell: Cell, outcome: dict, tactics: dict) -> dict:
    """Combine a cell's two calls into one record with totals and a status.

    Args:
        cell (Cell): The cell.
        outcome (dict): Recorded outcome call.
        tactics (dict): Recorded tactics call.

    Returns:
        dict: ``{n, model, effort, sweep, status, failures, calls, totals, grading}``.
            ``totals`` is only populated when both calls have valid usage.
    """
    failures = [f"{c['section']}: {f}" for c in (outcome, tactics) for f in c["failures"]]
    totals = None
    if outcome["usage"] and tactics["usage"] and outcome["cost"] and tactics["cost"]:
        in_tok = outcome["usage"]["input_tokens"] + tactics["usage"]["input_tokens"]
        out_tok = outcome["usage"]["output_tokens"] + tactics["usage"]["output_tokens"]
        totals = {
            "input_tokens": in_tok,
            "output_tokens": out_tok,
            "total_tokens": in_tok + out_tok,
            "input_usd": outcome["cost"]["input_usd"] + tactics["cost"]["input_usd"],
            "output_usd": outcome["cost"]["output_usd"] + tactics["cost"]["output_usd"],
            "total_usd": outcome["cost"]["total_usd"] + tactics["cost"]["total_usd"],
            "latency_s": round(outcome["latency_s"] + tactics["latency_s"], 2),
        }
    return {
        "n": cell.n, "model": cell.model, "effort": cell.effort, "sweep": cell.sweep,
        "status": "failed" if failures else "ok",
        "failures": failures,
        "calls": {"outcome": outcome, "tactics": tactics},
        "totals": totals,
        "grading": {"outcome_grounding": None, "motm": None, "tactics_grounding": None},
    }


def estimateCell(cell: Cell, context: dict) -> dict:
    """Estimate one cell's cost range from real payload size (no API call).

    Args:
        cell (Cell): The cell.
        context (dict): Output of load_match_context().

    Returns:
        dict: ``{n, input_tokens, output_tokens: (lo, hi), usd: (lo, hi)}``.
    """
    outcome_chars = len(json.dumps(context, indent=2))
    tactics_chars = len(json.dumps({k: context[k] for k in gen.TACTICS_SOURCE_KEYS}, indent=2))
    outcome_tokens = OUTCOME_INPUT_TOKENS.get(cell.model, OUTCOME_INPUT_TOKENS_DEFAULT)
    input_tokens = round(outcome_tokens * (1 + tactics_chars / outcome_chars))
    rate_in, rate_out = RATES[cell.model]
    out_lo, out_hi = OUTPUT_TOKEN_RANGE[cell.n]
    input_usd = input_tokens * rate_in / 1_000_000
    return {
        "n": cell.n,
        "input_tokens": input_tokens,
        "output_tokens": (out_lo, out_hi),
        "usd": (input_usd + out_lo * rate_out / 1_000_000, input_usd + out_hi * rate_out / 1_000_000),
    }


def withinCeiling(spent_usd: float, upcoming_high_usd: float, ceiling_usd: float = SPEND_CEILING_USD) -> bool:
    """Check that running the next cell can't push cumulative spend past the ceiling.

    Args:
        spent_usd (float): Recorded spend so far, failed attempts included.
        upcoming_high_usd (float): High-end estimate for the next cell.
        ceiling_usd (float): Hard cumulative ceiling.

    Returns:
        bool: True if the next cell is allowed to run.
    """
    return spent_usd + upcoming_high_usd <= ceiling_usd


def renderMarkdown(record: dict) -> str:
    """Render the results record as the Markdown results table (for the PR).

    Args:
        record (dict): The comparison JSON record.

    Returns:
        str: Markdown with the results table, per-cell notes, and — once set —
            the ready-to-paste routing decision text.
    """
    def fmt(value, spec: str) -> str:
        return "—" if value is None else format(value, spec)

    lines = [f"# Model & effort comparison — match {record['match_id']}", ""]
    if record.get("decision_log_text"):
        lines += ["## Routing decision (ready to paste into the SPEC Decision log)", "",
                  record["decision_log_text"], ""]
    lines += [
        "## Results", "",
        "Cost and tokens from each response's `usage` × the rate table. Grading columns are a "
        "manual read that **calls out errors rather than gating on pass/fail**: no eval system "
        "exists yet (Module 3), so a wrong claim is recorded, not disqualifying. n = 1 per cell "
        "and `effort` output is non-deterministic, so small differences are within noise.", "",
        "| # | model | effort | input_tok | output_tok | total_tok | input_$ | output_$ | total_$ "
        "| latency_s | outcome_grounding | motm | tactics_grounding |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for cell in record["cells"]:
        t = cell["totals"] or {}
        g = cell["grading"]
        lines.append(
            f"| {cell['n']} | {cell['model']} | {cell['effort'] or 'none'} "
            f"| {fmt(t.get('input_tokens'), ',')} | {fmt(t.get('output_tokens'), ',')} "
            f"| {fmt(t.get('total_tokens'), ',')} | {fmt(t.get('input_usd'), '.4f')} "
            f"| {fmt(t.get('output_usd'), '.4f')} | {fmt(t.get('total_usd'), '.4f')} "
            f"| {fmt(t.get('latency_s'), '.1f')} | {g['outcome_grounding'] or '—'} "
            f"| {g['motm'] or '—'} | {g['tactics_grounding'] or '—'} |"
        )
    lines += ["", f"Total recorded spend (failed attempts included): "
                  f"${record['spent_usd']:.4f} (ceiling ${record['spend_ceiling_usd']:.2f}).", ""]
    if record.get("routing"):
        lines += [f"**Chosen routing:** outcome → cell {record['routing']['outcome']}, "
                  f"tactics → cell {record['routing']['tactics']} (a default, to revisit once the eval "
                  "system exists).", ""]
    if record.get("motm"):
        lines += [f"**MOTM ({record['motm']['player']}):** {record['motm']['note']}", ""]
    lines += ["## Per-section breakdown", "",
              "Outcome and tactics are separate calls, so routing can differ per section.", "",
              "| # | section | input_tok | output_tok | total_$ | latency_s |", "|---|---|---|---|---|---|"]
    for cell in record["cells"]:
        for section, call in cell["calls"].items():
            usage, cost = call["usage"] or {}, call["cost"] or {}
            lines.append(f"| {cell['n']} | {section} | {fmt(usage.get('input_tokens'), ',')} "
                         f"| {fmt(usage.get('output_tokens'), ',')} | {fmt(cost.get('total_usd'), '.4f')} "
                         f"| {fmt(call['latency_s'], '.1f')} |")
    lines.append("")
    graded = [c for c in record["cells"] if c["grading"].get("notes")]
    if graded:
        lines += ["## Grading notes", ""]
        for cell in graded:
            lines.append(f"### Cell {cell['n']} — {cell['model']}, {cell['effort'] or 'none'}")
            lines += [f"- {note}" for note in cell["grading"]["notes"]]
            lines.append("")
    failed = [c for c in record["cells"] if c["status"] == "failed"]
    if failed:
        lines += ["## Failed cells", ""]
        lines += [f"- Cell {c['n']} ({c['model']}, {c['effort'] or 'none'}): " + "; ".join(c["failures"])
                  for c in failed]
        lines.append("")
    return "\n".join(lines)


def loadRecord() -> dict:
    """Load the existing results record, or start an empty one.

    Returns:
        dict: The comparison record.
    """
    if RESULTS_JSON.exists():
        return json.loads(RESULTS_JSON.read_text())
    return {
        "match_id": MATCH_ID,
        "created": date.today().isoformat(),
        "rates_usd_per_mtok": {m: {"input": r[0], "output": r[1]} for m, r in RATES.items()},
        "max_tokens": MAX_TOKENS,
        "spend_ceiling_usd": SPEND_CEILING_USD,
        "spent_usd": 0.0,
        "decision_log_text": None,
        "cells": [],
    }


def saveRecord(record: dict) -> None:
    """Write the JSON record and re-render the Markdown table next to it.

    Args:
        record (dict): The comparison record.
    """
    record["cells"].sort(key=lambda c: c["n"])
    RESULTS_JSON.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_JSON.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n")
    RESULTS_MD.write_text(renderMarkdown(record))


def slimRecord(record: dict) -> dict:
    """Reduce the results record to what a results page needs (no raw model outputs).

    Args:
        record (dict): The comparison JSON record.

    Returns:
        dict: Record-level fields plus, per cell, config, totals, grading, and per-call
            tokens/cost/latency. The raw outputs and full ``usage`` dicts are dropped.
    """
    def slimCall(call: dict) -> dict:
        usage, cost = call["usage"] or {}, call["cost"] or {}
        return {
            "section": call["section"], "model_served": call.get("model_served"),
            "stop_reason": call.get("stop_reason"), "latency_s": call["latency_s"],
            "input_tokens": usage.get("input_tokens"), "output_tokens": usage.get("output_tokens"),
            "cost_usd": cost.get("total_usd"),
        }

    cells = [
        {**{key: cell[key] for key in ("n", "model", "effort", "sweep", "status", "failures", "totals", "grading")},
         "calls": {section: slimCall(call) for section, call in cell["calls"].items()}}
        for cell in record["cells"]
    ]
    return {
        "match_id": record["match_id"], "created": record["created"], "max_tokens": record["max_tokens"],
        "rates_usd_per_mtok": record["rates_usd_per_mtok"], "spent_usd": record["spent_usd"],
        "routing": record.get("routing"), "motm": record.get("motm"),
        "decision_log_text": record.get("decision_log_text"), "cells": cells,
    }


def printEstimate(context: dict, cells: list[Cell]) -> float:
    """Print the pre-run spend estimate and return its high end.

    Args:
        context (dict): Output of load_match_context().
        cells (list[Cell]): Cells to estimate.

    Returns:
        float: Sum of the high-end USD estimates.
    """
    print(f"{'#':<3}{'model':<20}{'effort':<8}{'input_tok':>10}{'output_tok':>16}{'est. USD':>16}")
    lo_total = hi_total = 0.0
    for cell in cells:
        est = estimateCell(cell, context)
        lo_total += est["usd"][0]
        hi_total += est["usd"][1]
        print(f"{cell.n:<3}{cell.model:<20}{cell.effort or 'none':<8}{est['input_tokens']:>10,}"
              f"{est['output_tokens'][0]:>8,}-{est['output_tokens'][1]:<7,}"
              f"{est['usd'][0]:>8.2f}-{est['usd'][1]:<7.2f}")
    print(f"\nEstimated total: ${lo_total:.2f}-${hi_total:.2f}  (ceiling ${SPEND_CEILING_USD:.2f})")
    return hi_total


def main(argv: list[str] | None = None) -> None:
    """Run the comparison (or estimate it, or re-render it) from the command line.

    Args:
        argv (list[str] | None): Arguments; defaults to ``sys.argv[1:]``.
    """
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--dry-run", action="store_true", help="print the spend estimate; no API calls")
    parser.add_argument("--confirm-spend", action="store_true", help="required to make live, billed calls")
    parser.add_argument("--render-only", action="store_true", help="re-render the Markdown from the JSON")
    parser.add_argument("--export-site", metavar="PATH", help="write a slim copy of the record to PATH; no API calls")
    parser.add_argument("--cells", default="", help="comma-separated cell numbers to run (default: all)")
    parser.add_argument("--rerun", action="store_true", help="re-run cells that already have a record")
    args = parser.parse_args(argv)

    if args.render_only:
        RESULTS_MD.write_text(renderMarkdown(loadRecord()))
        print(f"Rendered → {RESULTS_MD}")
        return
    if args.export_site:
        Path(args.export_site).write_text(json.dumps(slimRecord(loadRecord()), indent=2, ensure_ascii=False) + "\n")
        print(f"Exported slim record → {args.export_site}")
        return

    wanted = {int(n) for n in args.cells.split(",") if n} or {c.n for c in CELLS}
    cells = [c for c in CELLS if c.n in wanted]

    data_dir = Path(__file__).parents[2] / "data" / "euro-2024" / str(MATCH_ID)
    context = gen.load_match_context(MATCH_ID, data_dir)

    if args.dry_run:
        printEstimate(context, cells)
        return
    if not args.confirm_spend:
        parser.error("live runs are billed — pass --confirm-spend (or --dry-run to see the estimate)")

    competition, _, match_label = fetch_match_info(MATCH_ID)
    record = loadRecord()
    done = {c["n"] for c in record["cells"]}

    for cell in cells:
        if cell.n in done and not args.rerun:
            print(f"Cell {cell.n}: already recorded — skipping (use --rerun to replace)")
            continue
        est_high = estimateCell(cell, context)["usd"][1]
        if not withinCeiling(record["spent_usd"], est_high):
            print(f"Cell {cell.n}: would risk exceeding ${SPEND_CEILING_USD:.2f} ceiling — stopping")
            break
        print(f"Cell {cell.n}: {cell.model} / {cell.effort or 'none'} ...", flush=True)
        outcome = runCall("outcome", cell, context, match_label, competition)
        tactics = runCall("tactics", cell, context, match_label, competition)
        summary = summarizeCell(cell, outcome, tactics)
        record["spent_usd"] += sum(c["cost"]["total_usd"] for c in (outcome, tactics) if c["cost"])
        record["cells"] = [c for c in record["cells"] if c["n"] != cell.n] + [summary]
        saveRecord(record)  # after every cell: a crash never loses paid results
        totals = summary["totals"]
        print(f"  {summary['status']}"
              + (f" — ${totals['total_usd']:.4f}, {totals['total_tokens']:,} tok, {totals['latency_s']}s"
                 if totals else f" — {'; '.join(summary['failures'])}"))

    print(f"Wrote {RESULTS_JSON.name} and {RESULTS_MD.name}; spent ${record['spent_usd']:.4f}")


if __name__ == "__main__":
    main()
