"""Orchestrate fetching Karel's Crypto and updating the JSON datasets."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .api import KarelsCryptoAPI
from .models import Crypto
from .storage import (
    HISTORY_PATH,
    LATEST_PATH,
    load_history,
    merge_history,
    save_history,
    save_latest,
)
from .transform import puzzle_to_crypto


def _collect_raw_puzzles(api: KarelsCryptoAPI) -> list[dict]:
    """Fetch every currently published puzzle, including the home puzzle."""
    nodes: dict[int, dict] = {}
    for node in api.get_published_puzzles(limit=100):
        nodes[int(node["id"])] = node

    home = api.get_home_puzzle()
    if home is not None:
        nodes[int(home["id"])] = home
    return list(nodes.values())


def build_datasets(raw_puzzles: list[dict]) -> tuple[list[Crypto], Crypto | None]:
    """Turn raw puzzle nodes into (history-with-solutions, latest-without).

    The newest puzzle (by date, then id) is treated as *this week's* puzzle and
    is returned without its solution. Every other puzzle is returned for the
    history dataset, keeping its solution.
    """
    cryptos = [puzzle_to_crypto(node) for node in raw_puzzles]
    if not cryptos:
        return [], None

    cryptos.sort(key=lambda c: (c.date, c.id))
    latest = cryptos[-1]
    history = [c for c in cryptos if c.id != latest.id]
    return history, latest.without_solution()


def run(
    *,
    endpoint: str | None = None,
    history_path: Path = HISTORY_PATH,
    latest_path: Path = LATEST_PATH,
    raw_puzzles: list[dict] | None = None,
) -> tuple[list[Crypto], Crypto | None]:
    """Scrape (or use provided raw data), merge and persist the datasets."""
    if raw_puzzles is None:
        api = KarelsCryptoAPI(endpoint) if endpoint else KarelsCryptoAPI()
        raw_puzzles = _collect_raw_puzzles(api)

    new_history, latest = build_datasets(raw_puzzles)

    merged = merge_history(load_history(history_path), new_history)
    save_history(merged, history_path)
    save_latest(latest, latest_path)
    return merged, latest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scrape Karel's Crypto into JSON datasets.")
    parser.add_argument(
        "--endpoint",
        default=None,
        help="Override the GraphQL endpoint (defaults to the De Standaard API).",
    )
    parser.add_argument(
        "--from-file",
        type=Path,
        default=None,
        help="Read raw puzzle nodes from a JSON file instead of the network "
        "(expects a list of puzzle nodes or a GraphQL response).",
    )
    parser.add_argument("--history", type=Path, default=HISTORY_PATH)
    parser.add_argument("--latest", type=Path, default=LATEST_PATH)
    args = parser.parse_args(argv)

    raw_puzzles = None
    if args.from_file is not None:
        raw_puzzles = _load_raw_from_file(args.from_file)

    history, latest = run(
        endpoint=args.endpoint,
        history_path=args.history,
        latest_path=args.latest,
        raw_puzzles=raw_puzzles,
    )

    latest_desc = f"{latest.title} ({latest.date})" if latest else "none"
    print(f"History: {len(history)} puzzles -> {args.history}")
    print(f"Latest:  {latest_desc} -> {args.latest}")
    return 0


def _load_raw_from_file(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        data = payload.get("data", payload)
        if "puzzles" in data:
            return data["puzzles"].get("data", [])
        if "published_puzzle" in data:
            node = data["published_puzzle"]
            return [node] if node else []
        return [payload]
    return list(payload)


if __name__ == "__main__":
    sys.exit(main())
