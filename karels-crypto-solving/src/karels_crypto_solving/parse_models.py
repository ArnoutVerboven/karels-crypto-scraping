"""Parse a gateway "models" HTML page into a model registry (availability + price).

Heuristic table extractor: pulls every ``<table>`` row, then per row picks the
cell that looks like a model id and the first two dollar amounts as input/output
price per 1M tokens. Writes ``model_registry.json``
(``{model: {input, output, available: true}}``) which ``pricing`` consults.

    karels-crypto-parse-models --html uploads/model_gateway/models.html

If your page isn't a simple table (e.g. a JS app), share the HTML structure and
this parser will be adapted to it.
"""

from __future__ import annotations

import argparse
import json
import re
from html.parser import HTMLParser
from pathlib import Path

_MODEL_RE = re.compile(r"^[a-z0-9][a-z0-9.\-:_]{3,}$", re.IGNORECASE)
_PRICE_RE = re.compile(r"\$\s*([0-9]+(?:\.[0-9]+)?)")  # only $-prefixed amounts
_DEFAULT_HTML = Path("uploads/model_gateway/models.html")
_DEFAULT_OUT = Path(__file__).resolve().parents[2] / "model_registry.json"


class _TableRows(HTMLParser):
    """Collect rows of cell-texts from all <table>s."""

    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._cell is not None:
            self._row.append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if self._row:
                self.rows.append(self._row)
            self._row = None

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)


def _looks_like_model(text: str) -> bool:
    # Model ids have a version marker (a digit or hyphen); this rejects plain
    # header words like "Model"/"Name".
    return (
        bool(_MODEL_RE.match(text))
        and ("-" in text or any(ch.isdigit() for ch in text))
        and not text.replace(".", "").isdigit()
    )


def extract_registry(html: str) -> dict[str, dict]:
    parser = _TableRows()
    parser.feed(html)
    registry: dict[str, dict] = {}
    for row in parser.rows:
        model = next((c for c in row if _looks_like_model(c)), None)
        if not model:
            continue
        prices = [float(m) for c in row for m in _PRICE_RE.findall(c)]
        entry: dict = {"available": True}
        if len(prices) >= 2:
            entry["input"], entry["output"] = prices[0], prices[1]
        registry[model] = entry
    return registry


def run(args: argparse.Namespace) -> int:
    html = Path(args.html).read_text(encoding="utf-8", errors="replace")
    registry = extract_registry(html)
    priced = sum(1 for v in registry.values() if "input" in v)
    Path(args.output).write_text(
        json.dumps(registry, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"Extracted {len(registry)} models ({priced} with prices) -> {args.output}")
    if registry:
        sample = list(registry.items())[:5]
        for m, v in sample:
            print(f"  {m}: {v}")
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
