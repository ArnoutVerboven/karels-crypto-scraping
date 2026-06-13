"""Query the Karel's Crypto GraphQL API and dump real responses.

Runs in GitHub Actions (full internet). Captures the live shape of the data so
the scraper/parser can be built and tested against reality. Output is written to
``recon_output/graphql/`` and uploaded as a workflow artifact.
"""

from __future__ import annotations

from pathlib import Path

import requests

ENDPOINT = "https://puzzelkc.standaard.be/graphql"
OUT = Path("recon_output/graphql")
OUT.mkdir(parents=True, exist_ok=True)

PUZZLE_FIELDS = """
    id
    title
    start_date
    solution
    published
    rows {
        id
        offset
        hint
        answer
        index
        numbers {
            id
            index
        }
    }
    legends {
        id
        number
        letter
    }
"""

GET_HOME_PUZZLE = "query getHomePuzzle {\n    published_puzzle {\n" + PUZZLE_FIELDS + "\n    }\n}"
GET_PUZZLES = (
    "query getPuzzles($limit: Int, $page: Int, $published: Boolean) {\n"
    "    puzzles(limit: $limit, page: $page, published: $published) {\n"
    "        data {\n" + PUZZLE_FIELDS + "\n        }\n        total\n    }\n}"
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (recon)",
    "Content-Type": "application/json",
    "Accept": "application/json",
}


def post(name: str, query: str, variables: dict | None = None) -> None:
    payload = {"query": query, "variables": variables or {}}
    try:
        resp = requests.post(ENDPOINT, json=payload, headers=HEADERS, timeout=30)
        print(f"POST {name} -> {resp.status_code} ({len(resp.content)} bytes)")
        (OUT / f"{name}.json").write_text(resp.text, encoding="utf-8")
        # Echo a trimmed preview to the logs.
        preview = resp.text[:1500]
        print(preview)
        print("..." if len(resp.text) > 1500 else "")
    except Exception as exc:  # noqa: BLE001
        print(f"POST {name} -> ERROR {exc}")


def main() -> int:
    post("getHomePuzzle", GET_HOME_PUZZLE)
    post("getPuzzles_published_p1", GET_PUZZLES,
         {"published": True, "page": 1, "limit": 6})
    # Grab a larger page to learn the archive size / total count.
    post("getPuzzles_published_p1_l100", GET_PUZZLES,
         {"published": True, "page": 1, "limit": 100})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
