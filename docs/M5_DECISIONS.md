# M5 decisions: the "what changed" brief

**Objective.** Every week, turn the M3 change log into a one-page memo a CI analyst would send
to a brand lead: approvals, late-stage readouts, new entrants, implications. Written by an LLM,
but **grounded**: the model sees only our structured change log, cites an ID for every claim,
and a guardrail rejects any brief that mentions an ID not in the input.

## Chunk 1: the brief input (`src/obesity_ci/brief/inputs.py`)

| Decision | Why | Cost |
|---|---|---|
| **The model sees only the change log plus each molecule's class and sponsor from our config.** | Grounding: anything in the brief must trace to a row we can show. Class and sponsor are our own curated facts, so the model can say "Takeda's DPP-4" without guessing. | The brief can't add outside context (e.g. a press release, analyst view). That's deliberate; a human adds it. |
| **Every high and medium change is sent; low changes up to 20, taken in turn from each change type.** | Keeps the prompt small and the brief focused. Taking turns stops 30 routine date moves from crowding out a single FDA labeling action (a test pins this). | Some low changes are not sent; their count is reported in `omitted`. |
| **"Primary label source changed" and "No longer returned" are never sent**, only counted. | They are about our pipeline (search fixes, search drift), not about the market, and need a human check first. | A real event hidden behind one of these needs the human check to surface. |
| **Hard cap of 80 rows.** | Cost and focus; a brief listing 200 changes isn't a brief. | Overflow is counted in `omitted["over_row_limit"]`. |
| **The input is saved next to the brief** (`briefs/<date>.input.json`). | Every brief keeps its evidence: anyone can check a sentence against the exact rows the model saw. | A small extra file per week. |
| **Missing values are empty strings, never "nan".** | The model would otherwise read "nan" as content. | None. |

**First real input (openFDA, 2026-11-24 → 2026-11-25):** 12 changes. Sent: 3 low (Takeda labeling
supplements for Nesina, Oseni and Kazano, NDA022271 / NDA022426 / NDA203414, 20-23 Nov 2026).
Not sent: 9 "Primary label source changed" rows, the expected one-off effect of the label search fix.

## Chunk 2: writing the brief (`src/obesity_ci/brief/generate.py`)

| Decision | Why | Cost |
|---|---|---|
| **Model: Claude Opus 5.5 (`claude-opus-5-5`), effort `medium`, adaptive thinking.** | One short call a week, so quality beats price. Thinking is always on for this model; effort is set explicitly so a change in the default can't silently change the brief. | About a few cents a week at this input size; more if a busy week sends 80 rows. |
| **Server-side fallback on** (`fallbacks: "default"`, beta `server-side-fallback-2026-07-01`). | If the model declines a request, the API retries it on Anthropic's recommended fallback model inside the same call, instead of the weekly job failing. | A fallback brief is written by a different model; the footer names the model that actually wrote it. |
| **The stop reason is checked before the text is read.** A refusal, a cut-off (`max_tokens`) or an answer with no headings raises `BriefError` and nothing is saved. | A half-written or refused brief must never look like a real one. | The week needs a re-run by hand. |
| **Fixed sections: Headlines, Approvals and regulatory, Late-stage trials, New entrants, Implications for orforglipron.** | Matches how a CI memo is read: what happened first, then "so what" for one brand. The brand lens is the M4 anchor, so the two parts of the project tell one story. | Another brand team needs `ANCHOR` changed. |
| **"Implications" bullets start with Watch / Act / No action, written as interpretation and still cited.** | Separates fact from opinion, and makes the brief something a brand lead can act on. | It is still the model's judgement; a human should read it before it goes out. |
| **Every factual sentence ends with its ID in [brackets]; the prompt's examples use dummy IDs (NCT00000000).** | Makes each sentence checkable against the input file, and gives chunk 3's guardrail something to check. A real-looking example ID could leak into a brief. | None. |
| **Code, not the model, writes the header (period, counts) and the footer (what was left out, who wrote it).** | Those are facts we already have; letting the model restate them only adds room for error. | None. |
| **A week with nothing to send gets a brief written by code, with no API call.** | Quiet weeks are real (CT.gov had 0 changes on 2026-11-25), and they shouldn't cost money or invite the model to fill space. | None. |
| **The client is passed in; tests use a fake one.** | Tests run offline, for free, and check the exact request we send (model, effort, fallback, that housekeeping rows never reach the model). | The fake can't catch a change in the real API; the real run in chunk 4 does. |
| **SDK pinned at `anthropic>=2.14`.** | The `fallbacks` and `output_config` parameters need a recent SDK. | None (2.14 is already installed). |
