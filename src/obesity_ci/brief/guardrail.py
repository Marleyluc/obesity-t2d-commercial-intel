"""The ID guardrail: a brief may only cite IDs that were in its input (M5, chunk 3).

The model writes the brief; this module decides whether we keep it. It checks the model's part
of the brief (not the header and footer, which our code writes) for four things:

1. Every ID-shaped token anywhere in the text (NCT numbers, NDA/BLA/ANDA numbers, 8-digit DINs)
   is one we sent. An unknown ID means the model reached outside the change log, the one thing
   a grounded brief must never do.
2. Every [bracketed] citation is an ID we sent, so a garbled citation like [NCT0123] fails too.
3. Every line that says something carries at least one citation (except "Nothing this week.").
4. The five section headings are all there, in order.

generate.run() calls check() after each draft. If it finds problems, the model gets ONE retry with
the problems listed; if the second draft also fails, nothing is saved as the brief.
"""

from __future__ import annotations

import re

# ID shapes we track. DINs are 8 digits; an NDA may be written "NDA 022271", so the space is allowed.
ID_PATTERN = re.compile(r"\b(?:NCT\d{8}|(?:NDA|BLA|ANDA) ?\d{6}|\d{8})\b")
CITATION = re.compile(r"\[([^\[\]]+)\]")
EMPTY_LINE = re.compile(r"^[-*\s]*nothing this week\.?\s*$", re.IGNORECASE)


def _norm(token: str) -> str:
    return token.replace(" ", "").strip().upper()


def cited_ids(body: str) -> set[str]:
    """Every ID inside [brackets], e.g. "[NDA022271; NDA022426]" gives both."""
    return {_norm(part) for group in CITATION.findall(body) for part in re.split(r"[,;]", group)
            if part.strip()}


def check(body: str, allowed: set[str], headings: list[str]) -> list[str]:
    """Problems with a draft; an empty list means it passes."""
    allowed = {_norm(a) for a in allowed}
    problems = []

    unknown = sorted({_norm(t) for t in ID_PATTERN.findall(body)} - allowed)
    if unknown:
        problems.append(f"Mentions IDs that are not in the change log: {', '.join(unknown)}.")

    parts = {part.strip() for group in CITATION.findall(body) for part in re.split(r"[,;]", group)}
    bad = sorted(p for p in parts if p and _norm(p) not in allowed and _norm(p) not in unknown)
    if bad:
        problems.append(f"Has citations that are not change-log IDs: {', '.join(bad)}.")

    uncited = [ln.strip() for ln in body.splitlines()
               if ln.strip() and not ln.lstrip().startswith("#") and not EMPTY_LINE.match(ln)
               and not CITATION.search(ln)]
    if uncited:
        shown = "; ".join(f'"{u[:80]}"' for u in uncited[:3])
        problems.append(f"{len(uncited)} line(s) state something without a [citation], e.g. {shown}.")

    found = [ln.strip() for ln in body.splitlines() if ln.startswith("## ")]
    if found != headings:
        problems.append(f"Headings should be exactly {headings}; found {found}.")
    return problems


def feedback(problems: list[str]) -> str:
    """The note added to the retry request."""
    return ("Your previous draft failed our automatic checks:\n- " + "\n- ".join(problems)
            + "\nWrite the brief again, following the rules exactly. Cite only IDs from the change "
              "log, end every line that states something with its [ID], and write \"Nothing this "
              "week.\" under any empty section.")
