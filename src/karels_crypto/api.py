"""Thin client for the Karel's Crypto GraphQL API.

The puzzle single-page-app at ``https://puzzelkc.standaard.be`` is backed by a
GraphQL endpoint. The queries below were reconstructed from the app's bundle.

Only the public (unauthenticated) read queries are used:

* ``published_puzzle`` - the current week's published puzzle.
* ``puzzles(published: true, ...)`` - the list of currently published puzzles
  (the API only keeps a handful online at a time, which is why we accumulate
  history in the repository).
"""

from __future__ import annotations

import requests

DEFAULT_ENDPOINT = "https://puzzelkc.standaard.be/graphql"

# Fields shared by every puzzle query, mirroring the SPA's GraphQL fragment.
_PUZZLE_FIELDS = """
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

GET_HOME_PUZZLE = "query getHomePuzzle {\n    published_puzzle {" + _PUZZLE_FIELDS + "}\n}"

GET_PUZZLES = (
    "query getPuzzles($limit: Int, $page: Int, $published: Boolean) {\n"
    "    puzzles(limit: $limit, page: $page, published: $published) {\n"
    "        data {" + _PUZZLE_FIELDS + "}\n"
    "        total\n"
    "    }\n}"
)


class GraphQLError(RuntimeError):
    """Raised when the GraphQL endpoint returns an error payload."""


class KarelsCryptoAPI:
    def __init__(
        self,
        endpoint: str = DEFAULT_ENDPOINT,
        *,
        session: requests.Session | None = None,
        timeout: int = 30,
    ) -> None:
        self.endpoint = endpoint
        self.timeout = timeout
        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "karels-crypto-scraping/0.1 (+https://github.com)",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
        )

    def _execute(self, query: str, variables: dict | None = None) -> dict:
        resp = self.session.post(
            self.endpoint,
            json={"query": query, "variables": variables or {}},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        payload = resp.json()
        if payload.get("errors"):
            raise GraphQLError(str(payload["errors"]))
        return payload["data"]

    def get_home_puzzle(self) -> dict | None:
        """Return the current week's published puzzle (raw GraphQL node)."""
        data = self._execute(GET_HOME_PUZZLE)
        return data.get("published_puzzle")

    def get_published_puzzles(self, *, limit: int = 100, page: int = 1) -> list[dict]:
        """Return all currently published puzzles (raw GraphQL nodes)."""
        data = self._execute(
            GET_PUZZLES, {"published": True, "limit": limit, "page": page}
        )
        puzzles = data.get("puzzles") or {}
        return puzzles.get("data") or []
