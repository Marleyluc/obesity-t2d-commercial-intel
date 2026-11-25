"""Offline tests for the M5 ID guardrail, and for the retry around it."""

import json
from types import SimpleNamespace as NS

import pytest

from obesity_ci.brief import generate as G
from obesity_ci.brief import guardrail as R

HEADS = G.headings("orforglipron")
ALLOWED = {"NDA022271", "NDA022426", "NCT05869903", "02512345"}


def brief(*lines_by_section):
    """A brief with one block of lines under each of the five headings."""
    return "\n\n".join(f"{h}\n\n{body}" for h, body in zip(HEADS, lines_by_section))


GOOD = brief("- Takeda filed two labeling supplements [NDA022271; NDA022426].",
             "Takeda updated the Nesina and Oseni labels [NDA022271, NDA022426].",
             "- A Phase 3 trial completed [NCT05869903].",
             "- Nothing this week.",
             "- Watch: a DPP-4 label update may be routine [NDA022271].")


def test_good_brief_passes():
    assert R.check(GOOD, ALLOWED, HEADS) == []
    assert R.cited_ids(GOOD) == {"NDA022271", "NDA022426", "NCT05869903"}


def test_id_from_memory_is_caught_even_outside_brackets():
    bad = GOOD.replace("may be routine", "mirrors Ozempic's NDA 209637 update")
    problems = R.check(bad, ALLOWED, HEADS)
    assert len(problems) == 1 and "NDA209637" in problems[0]


def test_dummy_prompt_example_and_garbled_citations_are_caught():
    bad = GOOD.replace("[NCT05869903]", "[NCT00000000]").replace("[NDA022271].", "[Nesina label].")
    problems = " ".join(R.check(bad, ALLOWED, HEADS))
    assert "NCT00000000" in problems and "Nesina label" in problems


def test_uncited_lines_and_wrong_headings_are_caught():
    bad = GOOD.replace(" [NCT05869903]", "").replace("## New entrants", "## New products")
    problems = R.check(bad, ALLOWED, HEADS)
    assert any("without a [citation]" in p for p in problems)
    assert any("Headings" in p for p in problems)


def test_a_din_is_an_id():
    assert R.check(GOOD.replace("- Nothing this week.", "- Novo listed a product [02512345]."), ALLOWED, HEADS) == []
    assert "02599999" in R.check(GOOD.replace("- Nothing this week.", "- Listed [02599999]."), ALLOWED, HEADS)[0]


# ---- the retry inside generate.run ----

INPUT = {"period": {"from": "2026-11-24", "to": "2026-11-25"},
         "counts": {"all_changes": 2, "sent": 2, "by_importance_sent": {"low": 2}},
         "omitted": {"needs_human_review": {}, "low_importance_not_sent": 0, "over_row_limit": 0},
         "changes": [{"id": i} for i in ["NDA022271", "NDA022426"]]}
ANCHOR = {"molecule": "orforglipron", "class": "GLP-1 receptor agonist (oral)", "sponsor": "Eli Lilly"}
FIRST_BAD = GOOD.replace("[NCT05869903]", "[NCT99999999]")
OK = GOOD.replace(" [NCT05869903]", " [NDA022426]")  # only IDs from INPUT


class ScriptedClient:
    """Returns the given drafts in order and keeps every request."""

    def __init__(self, *drafts):
        self.drafts, self.requests = list(drafts), []
        self.beta = NS(messages=NS(create=self._create))

    def _create(self, **kwargs):
        self.requests.append(kwargs)
        return NS(stop_reason="end_turn", model=G.MODEL, usage=NS(input_tokens=100, output_tokens=50),
                  content=[NS(type="text", text=self.drafts.pop(0))])


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.setattr(G.config, "ROOT", tmp_path)
    monkeypatch.setattr(G, "anchor_context", lambda: ANCHOR)
    (tmp_path / "briefs").mkdir()
    (tmp_path / "briefs" / "2026-11-25.input.json").write_text(json.dumps(INPUT))
    return tmp_path / "briefs"


def test_first_draft_passes_one_call(repo):
    client = ScriptedClient(OK)
    r = G.run(client=client)
    assert len(client.requests) == 1 and r["guardrail"] == {"attempts": 1, "citations": 2}
    assert "ID check passed: 2 distinct IDs cited" in r["brief"]


def test_bad_draft_is_retried_with_the_problems(repo):
    client = ScriptedClient(FIRST_BAD, OK)
    r = G.run(client=client)
    retry = client.requests[1]["messages"][0]["content"]
    assert "NCT99999999" in retry and "failed our automatic checks" in retry
    assert r["guardrail"]["attempts"] == 2 and r["input_tokens"] == 200  # both calls counted
    assert "NCT99999999" not in (repo / "2026-11-25.md").read_text()


def test_two_bad_drafts_save_nothing(repo):
    with pytest.raises(G.BriefError, match="failed the ID guardrail twice"):
        G.run(client=ScriptedClient(FIRST_BAD, FIRST_BAD))
    assert not (repo / "2026-11-25.md").exists()
    assert "REJECTED" in (repo / "2026-11-25.rejected.md").read_text()


# ---- a draft written outside the API (e.g. in the Claude app) ----

def test_outside_draft_is_checked_and_saved_without_any_client(repo):
    r = G.run(draft="Here you go:\n\n" + OK)
    assert r["model"] == G.DRAFT_AUTHOR and r["guardrail"]["attempts"] == 1
    assert "drafted in the Claude app" in (repo / "2026-11-25.md").read_text()


def test_bad_outside_draft_is_rejected_with_no_retry(repo):
    with pytest.raises(G.BriefError, match="failed the ID guardrail, so"):
        G.run(draft=FIRST_BAD)
    assert not (repo / "2026-11-25.md").exists()
