"""Offline tests for the M5 brief generator. A fake client stands in for the API: no key, no cost."""

import json
from types import SimpleNamespace as NS

import pytest

from obesity_ci.brief import generate as G

ANCHOR = {"molecule": "orforglipron", "class": "GLP-1 receptor agonist (oral)", "sponsor": "Eli Lilly"}
INPUT = {
    "period": {"from": "2026-11-24", "to": "2026-11-25"},
    "counts": {"all_changes": 12, "sent": 1, "by_importance_sent": {"low": 1}},
    "omitted": {"needs_human_review": {"Primary label source changed": 9},
                "low_importance_not_sent": 0, "over_row_limit": 0},
    "changes": [{"id": "NDA022271", "source": "FDA (Drugs@FDA and labels)", "change_type": "New FDA action",
                 "importance": "low", "molecules": "alogliptin", "classes": "DPP-4 inhibitor",
                 "sponsors": "Takeda", "title": "NESINA", "field": "event_type", "old": "",
                 "new": "Labeling change", "detail": "SUPPL-17; 2026-11-20"}],
}


class FakeClient:
    """Records the request and returns a canned response shaped like the SDK's."""

    def __init__(self, text="## Headlines\n\n- Takeda updated the Nesina label [NDA022271].",
                 stop_reason="end_turn"):
        self.request = None
        self.response = NS(stop_reason=stop_reason, model=G.MODEL,
                           usage=NS(input_tokens=900, output_tokens=300),
                           content=[NS(type="thinking", thinking=""), NS(type="text", text=text)])
        self.beta = NS(messages=NS(create=self._create))

    def _create(self, **kwargs):
        self.request = kwargs
        return self.response


def test_request_is_grounded_and_configured():
    fake = FakeClient()
    G.call_model(INPUT, fake, ANCHOR)
    req = fake.request
    assert req["model"] == "claude-opus-5-5" and req["output_config"] == {"effort": "medium"}
    assert req["fallbacks"] == "default" and req["betas"] == ["server-side-fallback-2026-07-01"]
    user = req["messages"][0]["content"]
    assert "NDA022271" in user and "orforglipron (Eli Lilly" in user  # the change log and the brand lens
    assert "Primary label source changed" not in user  # housekeeping rows never reach the model
    for h in G.headings():
        assert h in req["system"]


def test_text_before_first_heading_is_dropped_and_thinking_ignored():
    out = G.call_model(INPUT, FakeClient("Sure, here it is.\n\n## Headlines\n\n- x [NDA022271]"), ANCHOR)
    assert out["body"].startswith("## Headlines") and out["output_tokens"] == 300


@pytest.mark.parametrize("stop, text", [("refusal", ""), ("max_tokens", "## Headlines\n- cut"),
                                        ("end_turn", "No headings here.")])
def test_unusable_answers_raise(stop, text):
    with pytest.raises(G.BriefError):
        G.call_model(INPUT, FakeClient(text, stop), ANCHOR)


def test_render_adds_header_and_footer_from_code():
    md = G.render(INPUT, "## Headlines\n\n- x [NDA022271]", {"model": G.MODEL})
    assert md.startswith("# What changed: 2026-11-24 to 2026-11-25")
    assert "1 of 12 changes" in md
    assert '9 "Primary label source changed" rows' in md  # the reader sees what was held back


def test_empty_week_skips_the_api(tmp_path, monkeypatch):
    monkeypatch.setattr(G.config, "ROOT", tmp_path)
    monkeypatch.setattr(G, "anchor_context", lambda: ANCHOR)
    (tmp_path / "briefs").mkdir()
    empty = {**INPUT, "changes": [], "counts": {"all_changes": 0, "sent": 0, "by_importance_sent": {}}}
    (tmp_path / "briefs" / "2026-11-25.input.json").write_text(json.dumps(empty))

    class Boom:
        def __getattr__(self, name):
            raise AssertionError("the API must not be called for an empty week")

    r = G.run(client=Boom())
    assert r["out"].name == "2026-11-25.md" and r["model"] is None
    assert r["brief"].count("Nothing this week.") == len(G.SECTIONS) - 1
