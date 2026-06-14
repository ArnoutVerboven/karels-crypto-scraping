"""Analyse word-solver failures from a predictions dump (see karels-crypto-eval).

Produces quantitative stats and (optionally) an LLM-clustered breakdown of the
failure modes.

    karels-crypto-analyze-failures --predictions preds.json \
        --model gpt-5.5-2026-04-23 --output failures.json
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from . import config
from .optimization.program import normalise

logger = logging.getLogger(__name__)

CLUSTER_PROMPT = """\
Below are failed attempts at solving clues from "Karels Crypto", a Dutch/Flemish
cryptic word puzzle. For each: the clue, the correct answer, and the model's
(wrong) answer.

Group the failures into 4-7 distinct, non-overlapping FAILURE CATEGORIES that are
useful for understanding *why* the model fails (e.g. "plausible synonym but not
the cryptic answer", "missed a specific wordplay device", "wrong length",
"answer in wrong language / loanword confusion", "hallucinated non-word",
"too literal / surface reading"). 

Return ONLY JSON:
{"categories": [{"name": str, "description": str, "count": int,
                 "example_clues": [str, str]}]}
The counts should sum to roughly the number of failures shown.

Failures:
{listing}
"""


def quantitative(predictions: list[dict]) -> dict:
    total = len(predictions)
    failures = [p for p in predictions if not p["correct"]]
    blank = sum(1 for p in failures if not normalise(p.get("predicted") or ""))
    length_mismatch = sum(
        1 for p in failures
        if normalise(p.get("predicted") or "")
        and len(normalise(p["predicted"])) != len(normalise(p["expected"]))
    )
    return {
        "total": total,
        "correct": total - len(failures),
        "accuracy": (total - len(failures)) / total if total else 0.0,
        "failures": len(failures),
        "blank_or_unparseable": blank,
        "wrong_length": length_mismatch,
        "right_length_wrong_word": len(failures) - blank - length_mismatch,
    }


def cluster(failures: list[dict], model: str, max_items: int = 100) -> dict:
    client = config.openai_client()
    sample = failures[:max_items]
    listing = "\n".join(
        f"- clue: {p['cryptogram']!r} | correct: {p['expected']} | model: {p.get('predicted')!r}"
        for p in sample
    )
    kwargs = {"response_format": {"type": "json_object"}}
    if config.is_reasoning_model(model):
        kwargs["max_completion_tokens"] = config.REASONING_MIN_MAX_TOKENS
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": CLUSTER_PROMPT.format(listing=listing)}],
        **kwargs,
    )
    result = json.loads(resp.choices[0].message.content or "{}")
    result["clustered_items"] = len(sample)
    return result


def run(args: argparse.Namespace) -> int:
    data = json.loads(Path(args.predictions).read_text(encoding="utf-8"))
    predictions = data["predictions"]
    failures = [p for p in predictions if not p["correct"]]

    report = {
        "source": args.predictions,
        "model_evaluated": data.get("model"),
        "quantitative": quantitative(predictions),
    }
    if not args.no_cluster and failures:
        report["clusters"] = cluster(failures, args.model, args.max_items)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    q = report["quantitative"]
    print(f"accuracy {q['accuracy']:.1%} | {q['failures']} failures "
          f"(blank={q['blank_or_unparseable']}, wrong_len={q['wrong_length']}, "
          f"right_len_wrong={q['right_length_wrong_word']}) -> {out}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Analyse word-solver failures.")
    parser.add_argument("--predictions", required=True, help="A karels-crypto-eval dump.")
    parser.add_argument("--model", default="gpt-5.5-2026-04-23", help="LLM for clustering.")
    parser.add_argument("--max-items", type=int, default=100)
    parser.add_argument("--no-cluster", action="store_true", help="Skip the LLM clustering pass.")
    parser.add_argument("--output", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    config.load_env()
    return run(build_parser().parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
