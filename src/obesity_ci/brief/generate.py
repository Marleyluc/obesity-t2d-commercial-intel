"""Write the weekly "what changed" brief with Claude (M5, chunk 2).

Input:  briefs/<date>.input.json   (chunk 1: the only facts the model may use)
Output: briefs/<date>.md           (the memo a CI analyst would send a brand lead)

How it works:
1. The system prompt sets the job and the rules: use only the change log, cite an ID in square
   brackets for every claim, no numbers or events from memory, say "Nothing this week" when a
   section is empty.
2. The user message carries the change log as JSON, plus our anchor brand (orforglipron, from M4)
   so the "Implications" section is written from one brand's point of view.
3. Code, not the model, writes the header (period, counts) and the footer (what was left out and
   why). Those are facts we already have; letting the model restate them only adds risk.
4. A week with nothing to send gets a short brief written by code, with no API call.

The client is passed in, so tests use a fake one and never call the API (see
tests/test_brief_generate.py). Chunk 3 adds the ID guardrail between generating and saving.
"""

from __future__ import annotations

import json
from pathlib import Path

from obesity_ci import config

MODEL = "claude-opus-5-5"
EFFORT = "medium"  # the model's default, set explicitly so a default change can't surprise us
MAX_TOKENS = 8000  # a one-page brief is ~600-900 words; the rest is room for thinking
# If the model declines a request, the API retries it on Anthropic's recommended fallback model
# inside the same call instead of failing. A pharma brief shouldn't trigger this, but it costs
# nothing to have.
BETAS = ["server-side-fallback-2026-07-01"]
FALLBACKS = "default"

ANCHOR = "orforglipron"  # the M4 brand lens

SECTIONS = ["Headlines", "Approvals and regulatory", "Late-stage trials", "New entrants",
            "Implications for {brand}"]

SYSTEM = """You are a competitive-intelligence analyst in the obesity and type 2 diabetes market. \
Each week you turn a structured change log into a one-page brief for a brand lead. The brand lead \
is busy and commercial: they want to know what changed, who it affects, and what it means for \
their brand.

Grounding rules. These matter more than style:
- Use only the facts in the change log you are given. Each change has an "id" (an NCT number, an \
FDA application number such as NDA000000, or a Canadian DIN). Do not add drugs, results, dates, \
numbers, trial names or events that are not in the change log, even if you know them.
- End every sentence that states a fact with the ID or IDs it rests on, in square brackets, for \
example "A sponsor moved its Phase 3 trial to completed [NCT00000000]." Use only IDs that appear in \
the change log, copied exactly.
- The "classes" and "sponsors" fields are our own reference data, so you may use them to describe \
a change (for example "Takeda's DPP-4 inhibitor").
- A labeling change, a status change or a moved completion date is an event, not a result. Do not \
describe what a label now says or what a trial found unless the change log states it.
- If a section has no changes, write "Nothing this week." under it.

Format. Write Markdown with exactly these second-level headings, in this order:
{headings}
- Headlines: at most 3 bullets, the changes the brand lead most needs to know, most important \
first. Low-importance routine changes do not belong here unless nothing else happened.
- Approvals and regulatory: FDA actions, label updates, Health Canada and Ontario changes.
- Late-stage trials: status, phase, results-posted and completion-date changes for Phase 3 and \
Phase 2/3 trials, and Phase 2 trials only when they are high importance.
- New entrants: new trials and new products, grouped by sponsor.
- Implications for {brand}: 2 to 4 bullets on what these changes could mean for {brand}, from the \
brand team's point of view. Start each bullet with "Watch:", "Act:" or "No action:". This is your \
interpretation, so phrase it as such ("could", "may"), and still cite the IDs it rests on.
Group related changes into one sentence where you can (for example three labeling supplements \
from one sponsor). Keep the whole brief under 700 words. Start your answer with the first heading; \
do not add a title, greeting or sign-off."""


class BriefError(RuntimeError):
    """The model did not produce a usable brief (refusal, cut off, or empty)."""


def anchor_context(mols=None) -> dict:
    mols = config.molecules() if mols is None else mols
    row = mols[mols["generic"] == ANCHOR]
    if row.empty:
        return {"molecule": ANCHOR, "class": "", "sponsor": ""}
    r = row.iloc[0]
    return {"molecule": ANCHOR, "class": str(r["class_label"]), "sponsor": str(r["sponsor"])}


def headings(brand: str = ANCHOR) -> list[str]:
    return [f"## {s.format(brand=brand)}" for s in SECTIONS]


def system_prompt(brand: str = ANCHOR) -> str:
    return SYSTEM.format(brand=brand, headings="\n".join(headings(brand)))


def user_prompt(brief_input: dict, anchor: dict) -> str:
    period = brief_input["period"]
    return (
        f"Our brand: {anchor['molecule']} ({anchor['sponsor']}, {anchor['class']}).\n"
        f"Period: {period['from']} to {period['to']}.\n\n"
        "<change_log>\n"
        + json.dumps(brief_input["changes"], indent=1, ensure_ascii=False)
        + "\n</change_log>\n\nWrite this week's brief."
    )


def default_client():
    import anthropic

    key = config.secrets().anthropic_api_key
    if not key:
        raise BriefError("ANTHROPIC_API_KEY is empty. Add it to .env in the repo root "
                         "(ANTHROPIC_API_KEY=sk-ant-...), then run this again.")
    return anthropic.Anthropic(api_key=key)


def call_model(brief_input: dict, client, anchor: dict) -> dict:
    """One API call. Returns the brief body plus what we need to log (model, tokens)."""
    response = client.beta.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        betas=BETAS,
        fallbacks=FALLBACKS,
        thinking={"type": "adaptive"},
        output_config={"effort": EFFORT},
        system=system_prompt(anchor["molecule"]),
        messages=[{"role": "user", "content": user_prompt(brief_input, anchor)}],
    )
    # Check why the model stopped BEFORE reading the text.
    if response.stop_reason == "refusal":
        raise BriefError("The model declined to write this brief (and so did the fallback). "
                         "Check the input file for anything unusual.")
    if response.stop_reason == "max_tokens":
        raise BriefError(f"The brief was cut off at {MAX_TOKENS} tokens. Raise MAX_TOKENS or "
                         "send fewer changes.")
    text = "".join(b.text for b in response.content if b.type == "text").strip()
    if "## " not in text:
        raise BriefError("The model's answer has no section headings, so it isn't a brief.")
    text = text[text.index("## "):]  # drop anything before the first heading
    usage = response.usage
    return {"body": text, "model": response.model, "stop_reason": response.stop_reason,
            "input_tokens": usage.input_tokens, "output_tokens": usage.output_tokens}


def empty_body(brand: str = ANCHOR) -> str:
    """The brief for a week with nothing to send: written by code, no API call."""
    h = headings(brand)
    return "\n\n".join([h[0], "- No market changes in the sources we track this week."]
                       + [f"{x}\n\nNothing this week." for x in h[1:]])


def render(brief_input: dict, body: str, meta: dict) -> str:
    p, c, o = brief_input["period"], brief_input["counts"], brief_input["omitted"]
    header = (f"# What changed: {p['from']} to {p['to']}\n\n"
              f"*Obesity and T2D landscape brief. Based only on our change log: {c['sent']} of "
              f"{c['all_changes']} changes sent to the model. IDs in [brackets] link each claim to "
              f"a row in `briefs/{p['to']}.input.json`.*")
    left_out = []
    for change_type, n in o["needs_human_review"].items():
        left_out.append(f"- {n} \"{change_type}\" rows: pipeline housekeeping, held for a human check.")
    if o["low_importance_not_sent"]:
        left_out.append(f"- {o['low_importance_not_sent']} further low-importance changes.")
    if o["over_row_limit"]:
        left_out.append(f"- {o['over_row_limit']} changes over the row limit.")
    footer = "## Not covered in this brief\n\n" + ("\n".join(left_out) or "- Nothing was left out.")
    footer += f"\n\n*Written by {meta['model']}*" if meta.get("model") else "\n\n*No changes to send; written by code.*"
    return f"{header}\n\n{body}\n\n{footer}\n"


def input_path(date: str | None = None) -> Path:
    folder = config.ROOT / "briefs"
    files = sorted(folder.glob(f"{date or '*'}.input.json"))
    if not files:
        raise BriefError(f"No brief input{' for ' + date if date else ''} in {folder}. "
                         "Run scripts/build_brief_input.py first.")
    return files[-1]


def run(date: str | None = None, client=None) -> dict:
    src = input_path(date)
    brief_input = json.loads(src.read_text(encoding="utf-8"))
    anchor = anchor_context()
    if brief_input["changes"]:
        meta = call_model(brief_input, client or default_client(), anchor)
    else:
        meta = {"body": empty_body(anchor["molecule"]), "model": None}
    md = render(brief_input, meta["body"], meta)
    out = src.with_name(src.name.replace(".input.json", ".md"))
    out.write_text(md, encoding="utf-8")
    return {"input": src, "out": out, "brief": md, **{k: v for k, v in meta.items() if k != "body"}}
