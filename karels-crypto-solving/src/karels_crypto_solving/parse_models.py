"""Parse the AI-gateway "models" HTML page into a clean model registry.

The page nests, per provider (`<details><summary>Provider…`), tables whose
innermost rows are ``Models | Cost | Data classification``, where Cost looks
like ``Input: $0.5 / 1MTok, Output: $1.5 / 1MTok, …`` and Models may list several
comma-separated aliases.

Output ``model_registry.json``:
``{model: {input, output, provider, data_classification, available: true}}``.
``pricing.estimate_cost`` consults the ``input``/``output`` fields (USD per 1M
tokens), overriding the built-in table.

    karels-crypto-parse-models --html uploads/model_gateway/models.html
"""

from __future__ import annotations

import argparse
import json
import re
from html.parser import HTMLParser
from pathlib import Path

_MODEL_RE = re.compile(r"^[a-z0-9][a-z0-9.\-:_]+$", re.IGNORECASE)
_DOLLAR_RE = re.compile(r"\$\s*([0-9]+(?:\.[0-9]+)?)")
_RESIDENCY_RE = re.compile(r"\s+(?:US|EU|Global)\b.*$")
_DEFAULT_HTML = Path("uploads/model_gateway/models.html")
_DEFAULT_OUT = Path(__file__).resolve().parents[2] / "model_registry.json"


class _GatewayParser(HTMLParser):
    """Collect leaf table cells (no nested table) tagged with their provider."""

    def __init__(self) -> None:
        super().__init__()
        self.provider: str | None = None
        self._in_summary = False
        self._summary: list[str] = []
        self._stack: list[dict] = []
        self.leaves: list[tuple[str | None, str]] = []

    def handle_starttag(self, tag, attrs):
        if tag == "summary":
            self._in_summary, self._summary = True, []
        elif tag == "table" and self._stack:
            self._stack[-1]["has_table"] = True
        elif tag in ("td", "th"):
            self._stack.append({"text": [], "has_table": False, "provider": self.provider})

    def handle_endtag(self, tag):
        if tag == "summary":
            self._in_summary = False
            name = " ".join("".join(self._summary).split())
            self.provider = _RESIDENCY_RE.sub("", name).strip() or name
        elif tag in ("td", "th") and self._stack:
            cell = self._stack.pop()
            if not cell["has_table"]:
                self.leaves.append((cell["provider"], " ".join("".join(cell["text"]).split())))

    def handle_data(self, data):
        if self._in_summary:
            self._summary.append(data)
        elif self._stack:
            self._stack[-1]["text"].append(data)


def _cost(cell: str) -> tuple[float | None, float | None]:
    """Parse 'Input: $X / 1MTok, Output: $Y / 1MTok, …' -> (input, output)."""
    inp = out = None
    for field in cell.split(","):
        f = field.strip()
        m = _DOLLAR_RE.search(f)
        if not m:
            continue
        if f.startswith("Input:"):
            inp = float(m.group(1))
        elif f.startswith("Output:"):
            out = float(m.group(1))
    return inp, out


def _priced(entry: dict) -> bool:
    return bool(entry.get("input")) and bool(entry.get("output"))


def extract_registry(html: str) -> dict[str, dict]:
    """Build ``{model: entry}`` from the gateway HTML.

    Providers are re-listed across sections (notably the "Lite LLM" meta-proxy,
    which re-exports everything, often at $0). We keep the first *priced* entry
    (non-zero input+output) so each model is attributed to its native provider
    and real cost, and never let an unpriced duplicate overwrite it.
    """
    parser = _GatewayParser()
    parser.feed(html)
    registry: dict[str, dict] = {}
    for i, (provider, text) in enumerate(parser.leaves):
        if "Input:" not in text or "$" not in text or i == 0:
            continue
        inp, out = _cost(text)
        model_cell = parser.leaves[i - 1][1]
        for alias in model_cell.split(","):
            model = alias.strip()
            if not _MODEL_RE.match(model) or not any(c.isdigit() or c == "-" for c in model):
                continue
            entry: dict = {"available": True}
            if provider:
                entry["provider"] = provider
            if inp is not None:
                entry["input"] = inp
            if out is not None:
                entry["output"] = out
            old = registry.get(model)
            if old is None or (not _priced(old) and _priced(entry)):
                registry[model] = entry
    return registry


def run(args: argparse.Namespace) -> int:
    html = Path(args.html).read_text(encoding="utf-8", errors="replace")
    registry = extract_registry(html)
    priced = sum(1 for v in registry.values() if "input" in v and "output" in v)
    Path(args.output).write_text(
        json.dumps(registry, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    providers = sorted({v.get("provider", "?") for v in registry.values()})
    print(f"Extracted {len(registry)} models ({priced} with input+output) -> {args.output}")
    print(f"Providers: {', '.join(providers)}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Parse gateway models HTML -> registry JSON.")
    parser.add_argument("--html", default=str(_DEFAULT_HTML))
    parser.add_argument("--output", default=str(_DEFAULT_OUT))
    return parser


def main(argv: list[str] | None = None) -> int:
    return run(build_parser().parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
