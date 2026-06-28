"""OpenAI chat-completions pricing (USD per 1M tokens).

Used by the benchmark to estimate the cost of each model run. Prices are
input/output per 1,000,000 tokens. Keep this in sync with your provider's
price list; cost estimates use input + output tokens only (cached-input and
search pricing are ignored).
"""

from __future__ import annotations

import functools
import json
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Price:
    input: float  # USD per 1M input tokens
    output: float  # USD per 1M output tokens


# A generated registry (e.g. parsed from the gateway's models HTML) can extend
# or override the built-in table. JSON shape: {"<model>": {"input": x, "output": y}}.
_REGISTRY_PATH = Path(__file__).resolve().parents[2] / "model_registry.json"


@functools.cache
def _registry() -> dict[str, Price]:
    path = Path(os.environ.get("KARELS_CRYPTO_MODEL_REGISTRY", str(_REGISTRY_PATH)))
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {m: Price(float(v["input"]), float(v["output"])) for m, v in raw.items() if "input" in v}


# Keyed by model id. Aliases that share a price are listed separately so a
# lookup works whatever id you pass.
PRICING: dict[str, Price] = {
    # gpt-3.5
    "gpt-3.5-turbo": Price(0.5, 1.5),
    "gpt-3.5-turbo-0125": Price(0.5, 1.5),
    "gpt-3.5-turbo-1106": Price(1.5, 2.0),
    "gpt-3.5-turbo-16k": Price(3.0, 4.0),
    # gpt-4
    "gpt-4": Price(30.0, 60.0),
    "gpt-4-0314": Price(30.0, 60.0),
    "gpt-4-0613": Price(30.0, 60.0),
    "gpt-4-turbo": Price(10.0, 30.0),
    "gpt-4-turbo-2024-04-09": Price(10.0, 30.0),
    "gpt-4-turbo-preview": Price(10.0, 30.0),
    "gpt-4-0125-preview": Price(10.0, 30.0),
    "gpt-4-1106-preview": Price(10.0, 30.0),
    # gpt-4o
    "gpt-4o": Price(2.5, 10.0),
    "gpt-4o-2024-08-06": Price(2.5, 10.0),
    "gpt-4o-2024-11-20": Price(2.5, 10.0),
    "gpt-4o-2024-05-13": Price(5.0, 15.0),
    "gpt-4o-mini": Price(0.15, 0.6),
    "gpt-4o-mini-2024-07-18": Price(0.15, 0.6),
    "gpt-4o-search-preview": Price(2.5, 10.0),
    "gpt-4o-search-preview-2025-03-11": Price(2.5, 10.0),
    "gpt-4o-mini-search-preview": Price(0.15, 0.6),
    "gpt-4o-mini-search-preview-2025-03-11": Price(0.15, 0.6),
    # gpt-4.5
    "gpt-4.5-preview": Price(75.0, 150.0),
    "gpt-4.5-preview-2025-02-27": Price(75.0, 150.0),
    # gpt-4.1
    "gpt-4.1": Price(2.0, 8.0),
    "gpt-4.1-2025-04-14": Price(2.0, 8.0),
    "gpt-4.1-mini": Price(0.4, 1.6),
    "gpt-4.1-mini-2025-04-14": Price(0.4, 1.6),
    "gpt-4.1-nano": Price(0.1, 0.4),
    "gpt-4.1-nano-2025-04-14": Price(0.1, 0.4),
    # o-series (reasoning)
    "o1-preview": Price(15.0, 60.0),
    "o1-preview-2024-09-12": Price(15.0, 60.0),
    "o1": Price(15.0, 60.0),
    "o1-2024-12-17": Price(15.0, 60.0),
    "o3-mini": Price(1.1, 4.4),
    "o3-mini-2025-01-31": Price(1.1, 4.4),
    "o4-mini": Price(1.1, 4.4),
    "o4-mini-2025-04-16": Price(1.1, 4.4),
    "o3": Price(2.0, 8.0),
    "o3-2025-04-16": Price(2.0, 8.0),
    # gpt-5
    "gpt-5-2025-08-07": Price(1.25, 10.0),
    "gpt-5-chat-latest": Price(1.25, 10.0),
    "gpt-5.1-2025-11-13": Price(1.25, 10.0),
    "gpt-5-mini-2025-08-07": Price(0.25, 2.0),
    "gpt-5-nano-2025-08-07": Price(0.05, 0.4),
    "gpt-5.2-chat-latest": Price(1.75, 14.0),
    "gpt-5.3-chat-latest": Price(1.75, 14.0),
    "gpt-5.2-2025-12-11": Price(1.75, 14.0),
    "gpt-5.4-2026-03-05": Price(2.75, 16.5),
    "gpt-5.4-mini-2026-03-17": Price(0.825, 4.95),
    "gpt-5.4-nano-2026-03-17": Price(0.22, 1.375),
    "gpt-5.5-2026-04-23": Price(5.5, 33.0),
}


def price_for(model: str) -> Price | None:
    """Look up a model's price: generated registry first, then the built-in table."""
    return _registry().get(model) or PRICING.get(model)


def estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float | None:
    """USD cost for a model given token counts, or ``None`` if price unknown."""
    price = price_for(model)
    if price is None:
        return None
    return prompt_tokens / 1_000_000 * price.input + completion_tokens / 1_000_000 * price.output
