"""LLM benchmark with the human app's *Show letter* flow (issue #9).

For every clue the human solved in the benchmark app, the model guesses with no
letters shown; on a wrong guess one more letter is revealed, in the same order
the app used for the human (the attempt's stored ``revealOrder``, else the order
regenerated from its ``seed``), and it guesses again. The first reveal count at
which the model is right is its ``k_star`` for that clue. Accuracy is then a
matrix of word length x letters revealed: a clue counts as a success at every
reveal count >= ``k_star`` (more letters never hurt) and as a failure below it.

Subcommands:

* ``probe``  - one tiny call per candidate model; writes the ones that answer.
* ``run``    - the reveal loop for one model over the human's solved clues.
* ``report`` - matrices for the human and every model (markdown + json).

The human attempts come from ``scripts/export_human_attempts.py`` (read-only
Firestore export, slimmed to what this needs).
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import time
import unicodedata
import zlib
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import config, pricing, providers
from .providers import ProviderError
from .word_solver import solve_word

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SOURCES = [
    _REPO_ROOT / "karels-crypto-scraping" / "data" / "history.json",
    _REPO_ROOT / "karels-crypto-solving" / "data" / "ingested_puzzles.json",
]
DEFAULT_OUTPUT_DIR = _REPO_ROOT / "karels-crypto-solving" / "research" / "llm_reveal"
_RETRY_STATUS = {408, 409, 429, 500, 502, 503, 504, 529, None}


# --- the app's reveal order (port of karels-crypto-benchmark/src/game/word.ts) ---


def normalize(s: str) -> str:
    """Strip accents and case, like the app: "Première" -> "premiere"."""
    decomposed = unicodedata.normalize("NFD", s)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower()


def _imul(a: int, b: int) -> int:
    return (a * b) & 0xFFFFFFFF


def seeded_rng(seed: int):
    """mulberry32, bit-for-bit the app's ``seededRng``."""
    state = seed & 0xFFFFFFFF

    def rng() -> float:
        nonlocal state
        state = (state + 0x6D2B79F5) & 0xFFFFFFFF
        t = state
        t = _imul(t ^ (t >> 15), t | 1)
        t ^= (t + _imul(t ^ (t >> 7), t | 61)) & 0xFFFFFFFF
        return ((t ^ (t >> 14)) & 0xFFFFFFFF) / 4294967296

    return rng


def reveal_order_for(answer: str, seed: int) -> list[int]:
    pos = [i for i, ch in enumerate(normalize(answer)) if "a" <= ch <= "z"]
    rng = seeded_rng(seed)
    for i in range(len(pos) - 1, 0, -1):
        j = int(rng() * (i + 1))
        pos[i], pos[j] = pos[j], pos[i]
    return pos


def letters_only(s: str) -> str:
    return re.sub(r"[^a-z]", "", normalize(s))


def pattern_for(answer: str, order: list[int], k: int) -> str:
    """The board after ``k`` reveals: shown letters, "_" for unknown, hyphens kept."""
    norm = normalize(answer)
    shown = set(order[:k])
    return "".join(
        ch if (i in shown or not "a" <= ch <= "z") else "_" for i, ch in enumerate(norm)
    )


# --- clues ---------------------------------------------------------------------


def load_clues() -> dict[str, dict]:
    """clueId -> {text, answer}, with the app's ids (``<puzzleId>-<wordIndex>``)."""
    clues = {}
    for path in _SOURCES:
        if not path.exists():
            continue
        for p in json.loads(path.read_text(encoding="utf-8")):
            for i, w in enumerate(p["words"]):
                if isinstance(w.get("solution"), str) and w["solution"]:
                    clues[f"{p['id']}-{i}"] = {"text": w["cryptogram"], "answer": w["solution"]}
    return clues


def load_tasks(attempts_path: Path, outcomes=("solved",)) -> list[dict]:
    """The human's attempts with the given outcomes, joined with their clue."""
    clues = load_clues()
    tasks = []
    for a in json.loads(attempts_path.read_text(encoding="utf-8")):
        if a["outcome"] not in outcomes:
            continue
        clue = clues.get(a["clueId"])
        if clue is None:
            logger.warning("Unknown clue %s, skipped", a["clueId"])
            continue
        order = a.get("revealOrder")
        if not order:
            # v1 attempts have no seed: use a fixed one per clue, in the app's algorithm.
            seed = a.get("seed")
            if seed is None:
                seed = zlib.crc32(a["clueId"].encode())
            order = reveal_order_for(clue["answer"], seed)
        tasks.append(
            {
                "clueId": a["clueId"],
                "text": clue["text"],
                "answer": clue["answer"],
                "length": len(letters_only(clue["answer"])),
                "order": order,
                "orderFromApp": bool(a.get("revealOrder")),
            }
        )
    return tasks


# --- model calls ---------------------------------------------------------------


def _call(model: str, task: dict, k: int, effort: str | None, retries: int = 6):
    pattern = pattern_for(task["answer"], task["order"], k)
    delay = 5.0
    for attempt in range(retries + 1):
        try:
            return pattern, solve_word(
                task["text"], task["length"], pattern, model=model, reasoning_effort=effort
            )
        except Exception as exc:  # noqa: BLE001 - SDKs leak transport errors (httpx, …)
            if not isinstance(exc, ProviderError):
                # e.g. google-genai raises httpx.RemoteProtocolError on a dropped connection
                exc = ProviderError(f"{type(exc).__name__}: {exc}", None)
            if exc.status_code not in _RETRY_STATUS or attempt == retries:
                raise exc from None
            logger.info("%s retry %d after %s", model, attempt + 1, exc.status_code)
            time.sleep(delay)
            delay = min(delay * 2, 120)
    raise AssertionError("unreachable")


def solve_with_reveals(model: str, task: dict, effort: str | None) -> dict:
    target = letters_only(task["answer"])
    tries, p_tok, c_tok = [], 0, 0
    for k in range(task["length"]):  # k = length would show the whole word
        try:
            pattern, sol = _call(model, task, k, effort)
        except ProviderError as exc:
            return {"clueId": task["clueId"], "error": f"{exc.status_code}: {str(exc)[:200]}",
                    "tries": tries, "prompt_tokens": p_tok, "completion_tokens": c_tok}
        p_tok += sol.prompt_tokens
        c_tok += sol.completion_tokens
        ok = letters_only(sol.answer) == target
        tries.append({"k": k, "pattern": pattern, "guess": sol.answer, "correct": ok})
        if ok:
            break
    k_star = tries[-1]["k"] if tries and tries[-1]["correct"] else None
    return {"clueId": task["clueId"], "length": task["length"], "answer": task["answer"],
            "k_star": k_star, "tries": tries, "prompt_tokens": p_tok, "completion_tokens": c_tok}


def _effort_for(model: str, effort: str | None) -> str | None:
    """Fall back to no reasoning setting when a model rejects it (e.g. gemini-2.0)."""
    if not effort:
        return None
    try:
        providers.chat(model, "Reply with OK.", "OK?", max_tokens=64, reasoning_effort=effort)
        return effort
    except ProviderError as exc:
        if exc.status_code == 400:
            logger.info("%s rejects reasoning_effort=%s; running without it", model, effort)
            return None
        raise


def cmd_probe(args) -> int:
    candidates = list(dict.fromkeys(args.models + discover(args.discover)))
    ok, failed = [], {}

    def probe(model):
        try:
            providers.chat(model, "Reply with the single word OK.", "Say OK.",
                           max_tokens=1024, reasoning_effort=None)
            return model, None
        except ProviderError as exc:
            return model, f"{exc.status_code}: {str(exc)[:160]}"
        except Exception as exc:  # noqa: BLE001 - report any SDK failure per model
            return model, f"{type(exc).__name__}: {str(exc)[:160]}"

    with ThreadPoolExecutor(max_workers=8) as pool:
        for model, err in pool.map(probe, candidates):
            if err is None:
                ok.append(model)
            else:
                failed[model] = err
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"available": ok, "unavailable": failed}, indent=2) + "\n")
    print(f"available ({len(ok)}): {' '.join(ok)}")
    for m, e in failed.items():
        print(f"unavailable: {m} -> {e}")
    return 0


_NOT_CHAT = re.compile(
    r"(embed|tts|transcribe|realtime|audio|image|search|codex|deep-research|pro\b|-pro-|"
    r"moderation|whisper|dall|computer-use|live)",
    re.IGNORECASE,
)


def discover(patterns: list[str]) -> list[str]:
    """Gateway model ids matching ``patterns`` (e.g. new gpt-5.6 / gpt-6 names)."""
    if not patterns:
        return []
    try:
        ids = [m.id for m in config.openai_client().models.list()]
    except Exception as exc:  # noqa: BLE001 - listing is best-effort
        logger.warning("Model listing failed: %s", exc)
        return []
    print(f"gateway lists {len(ids)} models")
    rx = re.compile("|".join(patterns), re.IGNORECASE)
    found = sorted(m for m in ids if rx.search(m) and not _NOT_CHAT.search(m))
    print(f"discovered: {' '.join(found)}")
    return found


def cmd_run(args) -> int:
    tasks = load_tasks(Path(args.attempts))
    out = Path(args.output_dir) / f"{safe_name(args.model)}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    effort = _effort_for(args.model, args.reasoning_effort)
    logger.info("%s: %d clues, effort=%s", args.model, len(tasks), effort)

    with ThreadPoolExecutor(max_workers=args.num_threads) as pool:
        results = list(pool.map(lambda t: solve_with_reveals(args.model, t, effort), tasks))
    p_tok = sum(r["prompt_tokens"] for r in results)
    c_tok = sum(r["completion_tokens"] for r in results)
    payload = {
        "model": args.model,
        "provider": providers.provider_for(args.model),
        "reasoning_effort": effort,
        "n_clues": len(tasks),
        "errors": sum(1 for r in results if "error" in r),
        "prompt_tokens": p_tok,
        "completion_tokens": c_tok,
        "est_cost_usd": pricing.estimate_cost(args.model, p_tok, c_tok),
        "results": results,
    }
    out.write_text(json.dumps(payload, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    solved0 = sum(1 for r in results if r.get("k_star") == 0)
    print(f"{args.model}: {solved0}/{len(tasks)} with no letters, errors {payload['errors']}")
    return 0


def safe_name(model: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", model)


# --- matrices ------------------------------------------------------------------


def matrix(rows: list[tuple[int, int | None]]) -> dict:
    """(length, k_star or None) per clue -> {length: {k: [successes, total]}}.

    Each clue fills every reveal count 0..length-1 of its row: success when
    k >= k_star, failure below it (and everywhere when never solved).
    """
    m: dict[int, dict[int, list[int]]] = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    for length, k_star in rows:
        for k in range(length):
            cell = m[length][k]
            cell[1] += 1
            cell[0] += int(k_star is not None and k >= k_star)
    return {L: dict(v) for L, v in sorted(m.items())}


def render_matrix(title: str, m: dict, max_k: int) -> list[str]:
    head = "| letters \\ revealed | " + " | ".join(str(k) for k in range(max_k + 1)) + " |"
    lines = [f"### {title}", "", head, "| --- |" + " ---: |" * (max_k + 1)]
    for L, row in m.items():
        cells = []
        for k in range(max_k + 1):
            s = row.get(k)
            cells.append(f"{s[0] / s[1]:.0%} ({s[1]})" if s else "")
        lines.append(f"| {L} | " + " | ".join(cells) + " |")
    return lines + [""]


def cmd_report(args) -> int:
    attempts = json.loads(Path(args.attempts).read_text(encoding="utf-8"))
    tasks = {t["clueId"]: t for t in load_tasks(Path(args.attempts))}
    human_rows = [
        (tasks[a["clueId"]]["length"], a["revealedCount"])
        for a in attempts
        if a["outcome"] == "solved" and a["clueId"] in tasks
    ]
    runs = []
    for p in sorted(Path(args.output_dir).glob("runs/*.json")):
        runs.append(json.loads(p.read_text(encoding="utf-8")))

    def row_acc(rows):
        m = matrix(rows)
        tot = sum(s[1] for r in m.values() for s in r.values())
        return m, (sum(s[0] for r in m.values() for s in r.values()) / tot if tot else 0.0)

    hm, hacc = row_acc(human_rows)
    summary = [{"model": "human (Arnout)", "provider": "human", "n": len(human_rows),
                "solved_no_letters": sum(1 for _, k in human_rows if k == 0),
                "mean_k_star": _mean([k for _, k in human_rows]),
                "cell_accuracy": hacc, "never_solved": 0, "errors": 0, "est_cost_usd": None}]
    matrices = {"human (Arnout)": hm}
    for r in runs:
        ok = [x for x in r["results"] if "error" not in x]
        rows = [(x["length"], x["k_star"]) for x in ok]
        m, acc = row_acc(rows)
        matrices[r["model"]] = m
        summary.append({
            "model": r["model"], "provider": r["provider"], "n": len(ok),
            "solved_no_letters": sum(1 for x in ok if x["k_star"] == 0),
            "mean_k_star": _mean([x["k_star"] for x in ok if x["k_star"] is not None]),
            "cell_accuracy": acc, "never_solved": sum(1 for x in ok if x["k_star"] is None),
            "errors": r["errors"], "est_cost_usd": r.get("est_cost_usd"),
            "reasoning_effort": r.get("reasoning_effort"),
        })
    summary.sort(key=lambda s: -s["cell_accuracy"])
    max_k = max((t["length"] for t in tasks.values()), default=1) - 1

    n_app = sum(1 for t in tasks.values() if t["orderFromApp"])
    lines = [
        "# LLM vs human: letters revealed one at a time",
        "",
        f"Clues: the {len(human_rows)} clues Arnout solved in the benchmark app. Each model "
        "guesses with no letters shown; after a wrong guess one more letter is revealed in "
        f"the same order the app used for Arnout ({n_app} clues from the stored "
        "`revealOrder`, the rest from a fixed per-clue seed in the app's algorithm). Once "
        "right, the clue counts as solved at that reveal count and every higher one.",
        "",
        "**Cell accuracy** is the share of (clue, reveal count) cells that are successes, "
        "over every reveal count 0..length-1 of each clue: the average of the matrix below "
        "weighted by clues. **0 letters** = solved cold. **mean k\\*** = average letters "
        "needed when solved.",
        "",
        "| # | Model | Provider | Cell accuracy | 0 letters | mean k* | never | n | errors "
        "| effort | est. cost |",
        "| ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: |",
    ]
    for i, s in enumerate(summary, 1):
        cost = f"${s['est_cost_usd']:.2f}" if s.get("est_cost_usd") is not None else ""
        mk = f"{s['mean_k_star']:.2f}" if s["mean_k_star"] is not None else ""
        lines.append(
            f"| {i} | {s['model']} | {s['provider']} | {s['cell_accuracy']:.1%} | "
            f"{s['solved_no_letters']}/{s['n']} | {mk} | {s['never_solved']} | {s['n']} | "
            f"{s['errors']} | {s.get('reasoning_effort') or ''} | {cost} |"
        )
    lines += ["", "## Matrices (accuracy, clues per cell in brackets)", ""]
    for s in summary:
        lines += render_matrix(s["model"], matrices[s["model"]], max_k)
    if Path(args.probe).exists():
        probe = json.loads(Path(args.probe).read_text())
        if probe.get("unavailable"):
            lines += ["## Models the gateway did not serve", ""]
            lines += [f"- `{m}`: {e}" for m, e in probe["unavailable"].items()]
            lines.append("")
    out = Path(args.output_dir)
    (out / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    serial = {k: {str(L): {str(kk): v for kk, v in row.items()} for L, row in m.items()}
              for k, m in matrices.items()}
    (out / "summary.json").write_text(
        json.dumps({"summary": summary, "matrices": serial}, indent=1) + "\n", encoding="utf-8"
    )
    print("\n".join(lines[:len(summary) + 12]))
    return 0


def _mean(xs):
    return sum(xs) / len(xs) if xs else None


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    pr = sub.add_parser("probe")
    pr.add_argument("--models", nargs="*", default=[])
    pr.add_argument("--discover", nargs="*", default=[], help="regexes for gateway model ids")
    pr.add_argument("--output", required=True)
    r = sub.add_parser("run")
    r.add_argument("--model", required=True)
    r.add_argument("--attempts", required=True)
    r.add_argument("--reasoning-effort", choices=["minimal", "low", "medium", "high"],
                   default="low")
    r.add_argument("--num-threads", type=int, default=6)
    r.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR / "runs"))
    rep = sub.add_parser("report")
    rep.add_argument("--attempts", required=True)
    rep.add_argument("--probe", default=str(DEFAULT_OUTPUT_DIR / "models.json"))
    rep.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    return p


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    for noisy in ("httpx", "openai", "anthropic", "google_genai"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    config.load_env()
    args = build_parser().parse_args(argv)
    return {"probe": cmd_probe, "run": cmd_run, "report": cmd_report}[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
