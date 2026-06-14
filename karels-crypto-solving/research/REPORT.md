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

## 1. General capability (basic prompt, n=120)

- The task is **hard**: best model **gpt-5.5 = 33%**, gpt-5 = 28%; everything else ≤ 13%.
- **Reasoning models dominate.** Non-reasoning models are near-zero: gpt-4.1 6.7%,
  gpt-4.1-mini 5.0%, gpt-4o 1.7%, gpt-3.5-turbo 0.8%, gpt-4o-mini 0%.
- Clear capability ladder: `gpt-5.5 ≫ gpt-5 ≫ o4-mini ≈ gpt-5.4-mini ≈ gpt-5-mini ≫ 4.x family`.
- Model strength is by far the biggest lever (orders of magnitude more than prompt).

| Model | Acc | Model | Acc |
| --- | ---: | --- | ---: |
| gpt-5.5 | 33.3% | gpt-4.1 | 6.7% |
| gpt-5 | 28.3% | gpt-4.1-mini | 5.0% |
| o4-mini | 13.3% | gpt-5-nano | 3.3% |
| gpt-5.4-mini | 11.7% | gpt-4o | 1.7% |
| gpt-5-mini | 10.8% | gpt-3.5-turbo | 0.8% |
| | | gpt-4o-mini | 0.0% |

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

## 5. Next steps

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
