# Solving Karel's Crypto with LLMs — single-word solver

Concise findings for the word-level solver (one cryptic clue → one Dutch word).
Raw data for plots: `summary.json` (aggregated) and the per-experiment JSONs in
this folder. Dataset: 874 solved clues (scraped + 44 photo-ingested book puzzles).

Setup notes:
- "Basic prompt" = the minimal default instruction; "optimized" = DSPy-tuned.
- Capability uses `reasoning_effort=low`, a fixed 120-clue sample.
- Optimization: task model **gpt-5-mini** (low effort), proposer/reflection model
  **gpt-5.5**, held-out val = 88, bounded search budgets.
- Caveat: small val sets → ±~5 pp noise; treat deltas as indicative.

## 1. General capability (basic prompt, n=300, low effort)

Data: `research/capability_n300/` (~$15 total). Headline:
- The task is **hard**: best model **gpt-5.5 = 40%**, gpt-5 = 28%; everything else ≤ 17%.
- **Reasoning models dominate.** Non-reasoning models stay low: gpt-4.1 9.7%,
  gpt-4o 7.0%, gpt-3.5-turbo 2.7%, gpt-4o-mini 2.3%.
- Capability ladder: `gpt-5.5 ≫ gpt-5 ≫ gpt-5.4-mini ≈ o4-mini ≈ gpt-5-mini ≫ 4.x ≫ 3.5/4o-mini`.
- Model strength is by far the biggest lever (≫ prompt; cf. §3).

| Model | Acc | Model | Acc |
| --- | ---: | --- | ---: |
| gpt-5.5 | 40.0% | gpt-4.1 | 9.7% |
| gpt-5 | 28.3% | gpt-4.1-mini | 8.3% |
| gpt-5.4-mini | 17.3% | gpt-4o | 7.0% |
| o4-mini | 16.3% | gpt-5-nano | 6.3% |
| gpt-5-mini | 15.7% | gpt-3.5-turbo | 2.7% |
| | | gpt-4o-mini | 2.3% |

## 2. Failure modes (gpt-5-mini, full set n=874, acc 16.2%)

Quantitative (732 failures):
- **85% are "right length, wrong word"** (623) — it returns a valid Dutch word of
  the correct length but the wrong one. Only **15% wrong length** (108), ~0 blank (1).
- ⇒ The model isn't failing at format/length; it fails at the **cryptic step**.

LLM-clustered failure types (gpt-5.5 judge, top categories by count):
- **Surface-definition answers (36)** — answers the literal/surface meaning instead
  of the wordplay. *Dominant failure.*
- **Compound/charade not built (30)** — answer is a built-up compound; model gives a
  single synonym instead of composing parts.
- **Foreign / abbreviation / regional cue missed (12)** — `(Fr.)`, `(Eng.)`, place
  names, abbreviations, Flemish-specific terms.
- **Letter/sound-level manipulation missed (9)** — hidden words, homophones, resegmentation.
- **Malformed / copied fragments (7)**, **wrong sense of ambiguous word (6)**.

Key insight: failures are overwhelmingly **"too literal"** — the model treats clues
as definitions, not cryptic constructions.

### Word length (gpt-5-mini, n=874) — `length_analysis_gpt5mini.json`

Accuracy drops sharply with length; there's a **cliff after 6 letters**:

| length | 3–4 | 5–6 | 7–8 | 9–10 | 11+ |
| --- | ---: | ---: | ---: | ---: | ---: |
| accuracy | 27% | 30% | 12% | 10% | 11% |

- **Short answers (≤6 letters) are ~3× easier** than long ones (≥7). Length is a
  strong, cheap proxy for difficulty (combine with letters-revealed for a fuller
  difficulty model — see roadmap).

## 3. Effect of prompt optimization (gpt-5-mini, val=88, baseline 19.3%)

| Method | Optimized | Δ vs baseline |
| --- | ---: | ---: |
| **GEPA** | **27.3%** | **+8.0 pp** |
| MIPROv2 | 25.0% | +5.7 pp |
| COPRO | 20.5% | +1.2 pp |

- **GEPA > MIPROv2 ≫ COPRO.** GEPA's reflective, feedback-driven proposals win;
  COPRO's blind hill-climbing barely moves.
- Prompt optimization helps (~+40% relative for GEPA) but is a **small absolute
  lever vs. model choice** (cf. §1).
- Final-prompt analysis (length tracks effectiveness):
  - **COPRO** (~10 lines): generic "treat as cryptic, match the pattern" advice.
  - **MIPROv2** (terse, 1 line): a single sharpened instruction.
  - **GEPA** (~38 lines): a structured solving guide — enumerates cryptic devices
    (charade, hidden, reversal, container, deletion, anagram, homophone, double
    definition, bilingual puns), **plus concrete worked examples it learned from
    failures** (e.g. `uitermate leep → hyperlink` = hyper+link; archaic spelling
    `sterven → verwylen`; `fel betwiste wielerkoers → pedaalslag`) and Flemish
    spelling notes (`y` vs `ij`). The richer, example-grounded prompt is the most effective.

### What instructions actually work (original → optimized)

Comparing the bare baseline ("solve this cryptic clue, return the word") against
the tuned prompts, the instructions that move the needle for *this* puzzle:

- **"Don't stop at the obvious/surface synonym."** Highest-leverage line — it
  directly attacks the dominant failure (§2: 85% surface-definition answers).
  Present in both winners (GEPA, MIPROv2).
- **Name the cryptic mechanisms explicitly** (charade/compound, hidden word,
  reversal, container, deletion, anagram, homophone, double definition). All three
  optimizers added an explicit device list; the vague baseline wasn't enough.
- **Frame as definition + wordplay**, and especially **"build the answer from
  parts" (charade/compound decomposition)** — targets the 2nd-biggest failure.
- **Concrete worked examples beat abstract advice.** GEPA's edge came from
  embedding solved Karel clues *with* their decomposition (`hyper`+`link`), i.e.
  instruction-level "few-shot" grounding, not just a device list.
- **Encode Flemish/Dutch specifics**: archaic/variant spelling (`y`↔`ij`),
  bilingual puns (`(Fr.)`,`(Eng.)`), Belgian references — targets the
  "foreign/regional cue missed" cluster.
- **Less important:** strict length/format reminders (only ~15% of errors were
  length-related) and prompt *language* — COPRO wrote a fully-Dutch prompt yet
  gained least, so mechanism-specificity + examples matter more than language.

## 4. Transfer: optimize small → apply to large (val=88)

| | Baseline (basic) | + GEPA prompt (tuned on gpt-5-mini) | Δ |
| --- | ---: | ---: | ---: |
| gpt-5-mini | 19.3% | 27.3% | +8.0 pp |
| **gpt-5.5** | 48.9% | **52.3%** | **+3.4 pp** |

- A prompt optimized cheaply on the **small** model **transfers** to the large one
  and still helps (+3.4 pp on gpt-5.5) — useful, since optimizing directly on
  gpt-5.5 is slow/expensive.
- Transfer gain is **smaller** on the strong model (it already does much of the
  reasoning itself), i.e. **diminishing returns** from prompt scaffolding as base
  capability rises.

## 5. Cross-provider comparison — accuracy & cost (low effort)

Data: `research/cross_provider/` (total **$5.38**). To include the strongest
models affordably, sample size is **tiered** (cheap models n=120, mid n=60,
frontier n=30) on the same seed (smaller sets are subsets of the larger). All at
`reasoning_effort=low`. `*(n=…)*` marks the smaller tiers.

| Model | Provider | Acc | Correct/Total | Cost/correct† | In/Out tok |
| --- | --- | ---: | ---: | ---: | ---: |
| gemini-3.5-flash *(n=60)* | Google | **46.7%** | 28/60 | $0.023 | 5080/69894 |
| gpt-5.5-2026-04-23 *(n=30)* | OpenAI | 43.3% | 13/30 | $0.044 | 2749/18437 |
| gemini-3-flash-preview | Google | 40.8% | 49/120 | **$0.016** | 10107/255225 |
| gpt-5-2025-08-07 *(n=60)* | OpenAI | 38.3% | 23/60 | $0.050 | 5486/113632 |
| claude-opus-4-8 *(n=30)* | Anthropic | 36.7% | 11/30 | $0.038 | 4359/15794 |
| gpt-5-mini-2025-08-07 | OpenAI | 19.2% | 23/120 | $0.008 | 10918/95624 |
| claude-sonnet-4-5-20250929 *(n=60)* | Anthropic | 16.7% | 10/60 | $0.078 | 7937/50297 |
| gpt-4.1 | OpenAI | 13.3% | 16/120 | $0.018 | 11038/33733 |
| claude-haiku-4-5-20251001 | Anthropic | 7.5% | 9/120 | $0.064 | 15833/111516 |
| gpt-4o-mini | OpenAI | 5.8% | 7/120 | $0.002 | 11038/17796 |

†*Cost/correct = est. USD ÷ correct answers; comparable across tiers since both
scale with n. Absolute per-run cost is **not** comparable (different n).*

Insights:
- **No single provider dominates — the frontier of each clusters ~37–47%.**
  `gemini-3.5-flash` (47%), `gpt-5.5` (43%), `gemini-3-flash` (41%), `gpt-5` (38%)
  and `claude-opus-4-8` (37%) are a near-tie (and within each other's CIs at these
  n: ±~9 pp at n=30, ±~6 pp at n=60). The §1 story holds: **thinking/reasoning is
  the lever** — every top model is a reasoning model.
- **Google's `gemini-flash` line is the value winner.** `gemini-3-flash-preview`
  is both strong (41%) and the cheapest per correct among capable models
  ($0.016), and `gemini-3.5-flash` tops accuracy. Caveat: gemini "thinks" heavily
  by **default** (gemini-3-flash burned ~2,130 output tok/clue — its cost is mostly
  hidden reasoning), so it's effectively always at non-trivial effort.
- **Anthropic underperforms its price at low effort.** `claude-haiku` (7.5%) and
  `claude-sonnet-4-5` (17%) lag same-tier rivals; only `claude-opus-4-8` (37%)
  competes. Claude appears to **under-think** this Dutch cryptic task unless it's
  the strongest model — its newer models also need the `thinking:adaptive` API
  (handled in `providers.py`), and a higher effort/budget might close the gap.
- **Cheapest viable solver:** `gpt-5-mini` at **$0.008/correct** (19% acc) — best
  $/solve if you don't need top accuracy; `gpt-4o-mini`/`gpt-4.1` are cheap but
  weak (non-reasoning).
- Caveats: tiered, small n (wide CIs); `gemini-3-pro-preview` is in the registry
  but returned **404 (no project access)** on this gateway, so it's excluded.

## 6. Next steps

- **Bigger/cleaner eval:** evaluate on the full 874 (not samples) with seeds/CIs;
  current val=88/120 gives ±~5 pp noise.
- **Decent-reasoning optimization:** medium/high `reasoning_effort` on gpt-mini was
  *intractable in the CI time budget* on this gateway (very slow per call). Worth a
  longer, batched run — gpt-mini at higher effort likely raises both baseline and ceiling.
- **Reasoning-effort sweep** per model (low/med/high) to separate "thinking budget"
  from prompt effect.
- **Feed failure modes into the prompt/feedback:** the failure taxonomy (§2) maps
  directly onto GEPA's feedback channel — encode "don't answer the surface
  definition; build charades; honour `(Fr./Eng.)` cues" to target the dominant errors.
- **Helper-letter regime:** ingested puzzles lack the grid key, so all runs are
  `reveal=none`; capture the key (better OCR) to study partial-letter assistance.
- **Few-shot demos:** all runs are instruction-only; allowing demos (esp. in MIPROv2)
  is the obvious next lever but trades off the "no vocabulary" constraint.
- **Cross-provider follow-ups (§5):** larger n for tighter CIs; an effort sweep on
  Claude (its low-effort numbers look budget-starved); restore `gemini-3-pro`
  access (404 today); and optimize a prompt *per provider* (the GEPA prompt was
  tuned on OpenAI — it may transfer differently to Gemini/Claude).
