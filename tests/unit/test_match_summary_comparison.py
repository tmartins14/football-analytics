"""Unit tests for the match-summary model/effort comparison harness. No network calls.

Covers SPEC Module 2 / Task 2's experiment-correctness rules (cost comes from
``usage`` x the rate table; a call without usable ``usage`` is a failed call)
and the acceptance criteria that no sampling parameters are sent and that
``effort`` is omitted for models that don't support it.
"""

from types import SimpleNamespace

import pytest

from ai.match_summary import compare_models as cmp
from ai.match_summary import generate_match_summary as gen

SAMPLING_PARAMS = {"temperature", "top_p", "top_k"}


def fakeResponse(usage="default", stop="end_turn", parsed="default", content=None, model="claude-sonnet-5"):
    """Build a stand-in for an Anthropic response with just the fields the harness reads."""
    if usage == "default":
        usage = {"input_tokens": 1000, "output_tokens": 200}
    if parsed == "default":
        parsed = {"headline": "h", "key_stats": [], "standout_performers": []}
    return SimpleNamespace(
        usage=None if usage is None else SimpleNamespace(model_dump=lambda: dict(usage)),
        stop_reason=stop,
        parsed_output=None if parsed is None else SimpleNamespace(model_dump=lambda: parsed),
        content=content if content is not None else [SimpleNamespace(type="text", text="prose")],
        model=model,
    )


class TestComputeCost:
    @pytest.mark.parametrize("model,rate_in,rate_out", [
        ("claude-haiku-4-5", 1, 5), ("claude-sonnet-5", 2, 10), ("claude-opus-5", 5, 25),
    ])
    def test_one_million_tokens_each_way_equals_the_rate_table(self, model, rate_in, rate_out):
        cost = cmp.computeCost({"input_tokens": 1_000_000, "output_tokens": 1_000_000}, model)
        assert cost == {"input_usd": rate_in, "output_usd": rate_out, "total_usd": rate_in + rate_out}

    def test_uses_usage_counts_not_estimates(self):
        cost = cmp.computeCost({"input_tokens": 224_520, "output_tokens": 3_000}, "claude-sonnet-5")
        assert cost["total_usd"] == pytest.approx(224_520 * 2 / 1e6 + 3_000 * 10 / 1e6)

    def test_unknown_model_raises(self):
        with pytest.raises(KeyError):
            cmp.computeCost({"input_tokens": 1, "output_tokens": 1}, "claude-unknown")


class TestValidateUsage:
    def test_complete_usage_has_no_problems(self):
        assert cmp.validateUsage({"input_tokens": 5, "output_tokens": 6}) == []

    def test_none_is_a_problem(self):
        assert cmp.validateUsage(None) == ["missing usage"]

    def test_missing_output_tokens_is_a_problem(self):
        assert cmp.validateUsage({"input_tokens": 5}) == ["usage.output_tokens missing"]

    def test_nonzero_cache_tokens_are_flagged(self):
        problems = cmp.validateUsage({"input_tokens": 5, "output_tokens": 6, "cache_read_input_tokens": 9})
        assert any("cache_read_input_tokens" in p for p in problems)


class TestMakeCall:
    def test_valid_outcome_call_records_config_cost_and_output(self):
        call = cmp.makeCall("outcome", "claude-sonnet-5", "low", fakeResponse(), 1.234)
        assert call["failures"] == []
        assert call["cost"]["total_usd"] == pytest.approx(1000 * 2 / 1e6 + 200 * 10 / 1e6)
        assert (call["effort"], call["model_requested"], call["max_tokens"]) == ("low", "claude-sonnet-5", cmp.MAX_TOKENS)
        assert call["latency_s"] == 1.23
        assert call["output"]["headline"] == "h"

    def test_tactics_text_joins_text_blocks_and_ignores_thinking(self):
        content = [SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text="para")]
        call = cmp.makeCall("tactics", "claude-opus-5", "medium", fakeResponse(content=content), 2.0)
        assert call["output"] == "para"
        assert call["failures"] == []

    def test_missing_usage_is_a_failed_call_with_no_cost(self):
        call = cmp.makeCall("outcome", "claude-sonnet-5", "low", fakeResponse(usage=None), 1.0)
        assert "missing usage" in call["failures"]
        assert call["cost"] is None

    @pytest.mark.parametrize("stop", ["max_tokens", "refusal"])
    def test_non_end_turn_stop_is_a_failed_call(self, stop):
        call = cmp.makeCall("outcome", "claude-sonnet-5", "low", fakeResponse(stop=stop), 1.0)
        assert f"stop_reason={stop}" in call["failures"]

    def test_no_parsed_output_is_a_failed_call(self):
        call = cmp.makeCall("outcome", "claude-sonnet-5", "low", fakeResponse(parsed=None), 1.0)
        assert "no output" in call["failures"]


class TestSummarizeCell:
    cell = cmp.CELLS[1]

    def calls(self, **tactics_kwargs):
        outcome = cmp.makeCall("outcome", self.cell.model, self.cell.effort,
                               fakeResponse(usage={"input_tokens": 100, "output_tokens": 10}), 1.0)
        tactics_kwargs = {"usage": {"input_tokens": 50, "output_tokens": 20}, **tactics_kwargs}
        tactics = cmp.makeCall("tactics", self.cell.model, self.cell.effort, fakeResponse(**tactics_kwargs), 2.0)
        return outcome, tactics

    def test_ok_cell_sums_both_calls(self):
        summary = cmp.summarizeCell(self.cell, *self.calls())
        assert summary["status"] == "ok"
        assert summary["totals"]["input_tokens"] == 150
        assert summary["totals"]["output_tokens"] == 30
        assert summary["totals"]["total_tokens"] == 180
        assert summary["totals"]["latency_s"] == 3.0
        assert summary["totals"]["total_usd"] == pytest.approx(150 * 2 / 1e6 + 30 * 10 / 1e6)

    def test_grading_starts_null_because_scoring_is_manual(self):
        summary = cmp.summarizeCell(self.cell, *self.calls())
        assert summary["grading"] == {"outcome_grounding": None, "motm": None, "tactics_grounding": None}

    def test_one_failed_call_fails_the_cell(self):
        summary = cmp.summarizeCell(self.cell, *self.calls(stop="max_tokens"))
        assert summary["status"] == "failed"
        assert summary["failures"] == ["tactics: stop_reason=max_tokens"]

    def test_missing_usage_leaves_totals_unset(self):
        summary = cmp.summarizeCell(self.cell, *self.calls(usage=None))
        assert summary["totals"] is None


class TestCellTable:
    def test_five_cells_matching_the_spec(self):
        assert [(c.model, c.effort) for c in cmp.CELLS] == [
            ("claude-haiku-4-5", None), ("claude-sonnet-5", "medium"), ("claude-opus-5", "medium"),
            ("claude-sonnet-5", "low"), ("claude-sonnet-5", "high"),
        ]

    def test_every_cell_model_has_a_rate(self):
        assert {c.model for c in cmp.CELLS} <= set(cmp.RATES)

    def test_every_cell_has_an_output_estimate(self):
        assert {c.n for c in cmp.CELLS} == set(cmp.OUTPUT_TOKEN_RANGE)


class TestSpendCeiling:
    def test_allows_a_cell_that_fits(self):
        assert cmp.withinCeiling(1.0, 1.4, ceiling_usd=7.0)

    def test_blocks_a_cell_that_could_cross_the_ceiling(self):
        assert not cmp.withinCeiling(6.0, 1.4, ceiling_usd=7.0)

    def test_exactly_at_ceiling_is_allowed(self):
        assert cmp.withinCeiling(5.6, 1.4, ceiling_usd=7.0)


class TestRequestKwargs:
    """What actually goes on the wire — the SPEC's 'no sampling params, effort only where supported'."""

    context = {key: {} for key in ("match_stats", "substitutes", "formation", "team_shape",
                                   "progressive_map", "pass_network")}

    @pytest.fixture
    def sent(self, monkeypatch):
        calls = []

        class FakeMessages:
            def parse(self, **kwargs):
                calls.append(kwargs)
                return fakeResponse()

            def create(self, **kwargs):
                calls.append(kwargs)
                return fakeResponse()

        monkeypatch.setattr(gen, "_build_client", lambda: SimpleNamespace(messages=FakeMessages()))
        return calls

    def test_effort_kwargs_none_omits_output_config(self):
        assert gen._effort_kwargs(None) == {}
        assert gen._effort_kwargs("low") == {"output_config": {"effort": "low"}}

    @pytest.mark.parametrize("request_fn", ["_request_outcome", "_request_tactics"])
    def test_haiku_cell_sends_no_effort(self, sent, request_fn):
        getattr(gen, request_fn)(self.context, "A vs B", "Comp", "claude-haiku-4-5", None, 16000)
        assert "output_config" not in sent[0]

    @pytest.mark.parametrize("request_fn", ["_request_outcome", "_request_tactics"])
    def test_effort_is_sent_when_given(self, sent, request_fn):
        getattr(gen, request_fn)(self.context, "A vs B", "Comp", "claude-sonnet-5", "medium", 16000)
        assert sent[0]["output_config"] == {"effort": "medium"}
        assert sent[0]["model"] == "claude-sonnet-5"
        assert sent[0]["max_tokens"] == 16000

    def test_no_sampling_params_on_any_cell_or_public_path(self, sent):
        for cell in cmp.CELLS:
            gen._request_outcome(self.context, "A vs B", "Comp", cell.model, cell.effort, cmp.MAX_TOKENS)
            gen._request_tactics(self.context, "A vs B", "Comp", cell.model, cell.effort, cmp.MAX_TOKENS)
        gen.generate_outcome_section(self.context, "A vs B", "Comp")
        gen.generate_tactics_section(self.context, "A vs B", "Comp")
        assert len(sent) == 2 * len(cmp.CELLS) + 2
        assert all(not SAMPLING_PARAMS & set(kwargs) for kwargs in sent)

    def test_public_generators_keep_their_shipped_config(self, sent):
        gen.generate_outcome_section(self.context, "A vs B", "Comp")
        gen.generate_tactics_section(self.context, "A vs B", "Comp")
        outcome, tactics = sent
        assert (outcome["model"], outcome["max_tokens"], outcome["output_config"]) == (
            gen.MODEL, 4096, {"effort": gen.OUTCOME_EFFORT})
        assert (tactics["model"], tactics["max_tokens"], tactics["output_config"]) == (
            gen.MODEL, 1500, {"effort": gen.TACTICS_EFFORT})


class TestRenderMarkdown:
    def record(self, cells):
        return {"match_id": 3943043, "spent_usd": 0.5, "spend_ceiling_usd": 7.0,
                "decision_log_text": None, "cells": cells}

    def test_ungraded_cell_shows_dashes_and_costs_from_totals(self):
        outcome = cmp.makeCall("outcome", "claude-sonnet-5", "low", fakeResponse(), 1.0)
        tactics = cmp.makeCall("tactics", "claude-sonnet-5", "low", fakeResponse(), 2.0)
        md = cmp.renderMarkdown(self.record([cmp.summarizeCell(cmp.CELLS[3], outcome, tactics)]))
        assert "| 4 | claude-sonnet-5 | low | 2,000 | 400 | 2,400 |" in md
        row = next(line for line in md.splitlines() if line.startswith("| 4 | claude-sonnet-5 | low"))
        assert row.endswith("| — | — | — |")

    def test_per_section_breakdown_and_grading_notes_are_rendered(self):
        outcome = cmp.makeCall("outcome", "claude-sonnet-5", "low", fakeResponse(), 1.0)
        tactics = cmp.makeCall("tactics", "claude-sonnet-5", "low", fakeResponse(), 2.0)
        summary = cmp.summarizeCell(cmp.CELLS[3], outcome, tactics)
        summary["grading"]["notes"] = ["Walker claim is contradicted by the data"]
        md = cmp.renderMarkdown(self.record([summary]))
        assert "| 4 | outcome | 1,000 | 200 |" in md
        assert "| 4 | tactics | 1,000 | 200 |" in md
        assert "### Cell 4 — claude-sonnet-5, low" in md
        assert "- Walker claim is contradicted by the data" in md

    def test_failed_cells_are_listed(self):
        outcome = cmp.makeCall("outcome", "claude-haiku-4-5", None, fakeResponse(stop="max_tokens"), 1.0)
        tactics = cmp.makeCall("tactics", "claude-haiku-4-5", None, fakeResponse(), 1.0)
        md = cmp.renderMarkdown(self.record([cmp.summarizeCell(cmp.CELLS[0], outcome, tactics)]))
        assert "## Failed cells" in md
        assert "outcome: stop_reason=max_tokens" in md
