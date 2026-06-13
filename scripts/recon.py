"""Reconnaissance helper for discovering the Karel's Crypto data source.

This script is meant to run inside a GitHub Actions runner (which has full
outbound internet access). It fetches the puzzle single-page-app, follows the
JavaScript bundles, greps them for likely API/asset URLs and probes a list of
candidate endpoints. Everything is written to ``recon_output/`` so the raw
material can be uploaded as a workflow artifact and inspected offline.

The goal is purely investigative: figure out *where* and in *what shape* the
puzzle data is served so the real scraper/parser can be written against it.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests

OUT = Path("recon_output")
OUT.mkdir(exist_ok=True)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "*/*",
    "Accept-Language": "nl-BE,nl;q=0.9,en;q=0.8",
}

BASE = "https://puzzelkc.standaard.be/"

# Candidate endpoints to probe. We genuinely don't know the API yet, so we try a
# broad set of common SPA / Flutter / Q42-42puzzles locations.
CANDIDATE_PATHS = [
    "version.json",
    "manifest.json",
    "flutter_bootstrap.js",
    "main.dart.js",
    "flutter_service_worker.js",
    "assets/AssetManifest.json",
    "assets/AssetManifest.bin.json",
    "assets/FontManifest.json",
    "assets/NOTICES",
    "api/crypto",
    "api/cryptos",
    "api/puzzle",
    "api/puzzles",
    "api/latest",
    "api/current",
    "api/week",
    "api/v1/crypto",
    "data/crypto.json",
    "data/latest.json",
    "crypto.json",
    "latest.json",
]

CANDIDATE_ABSOLUTE = [
    "https://api.42puzzles.com/hub/mediahuis/server?path=/puzzels/karels-crypto&brand=ds",
    "https://api.42puzzles.com/hub/mediahuis/configs",
]

URL_RE = re.compile(r"""https?://[^\s"'`)]+""")
PATH_RE = re.compile(r"""["'`](/[A-Za-z0-9_\-./]+?\.(?:json|js))["'`]""")


def save(name: str, content: bytes) -> None:
    path = OUT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    print(f"  saved {path} ({len(content)} bytes)")


def fetch(url: str, timeout: int = 30) -> requests.Response | None:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout)
        print(f"GET {url} -> {resp.status_code} ({len(resp.content)} bytes, "
              f"{resp.headers.get('content-type', '?')})")
        return resp
    except Exception as exc:  # noqa: BLE001 - recon should never crash
        print(f"GET {url} -> ERROR {exc}")
        return None


def main() -> int:
    report: dict[str, object] = {"base": BASE, "endpoints": {}}

    index = fetch(BASE)
    if index is not None:
        save("index.html", index.content)
        report["index_status"] = index.status_code

    discovered: set[str] = set()
    js_urls: set[str] = set()

    if index is not None:
        text = index.text
        for m in re.finditer(r"""(?:src|href)=["']([^"']+)["']""", text):
            ref = m.group(1)
            full = urljoin(BASE, ref)
            discovered.add(full)
            if full.endswith(".js"):
                js_urls.add(full)
        # Flutter apps load flutter_bootstrap.js even if not in static HTML.
        js_urls.add(urljoin(BASE, "flutter_bootstrap.js"))
        js_urls.add(urljoin(BASE, "main.dart.js"))

    # Probe candidate endpoints (relative + absolute).
    for path in CANDIDATE_PATHS:
        url = urljoin(BASE, path)
        resp = fetch(url)
        if resp is None:
            continue
        report["endpoints"][url] = {  # type: ignore[index]
            "status": resp.status_code,
            "content_type": resp.headers.get("content-type"),
            "length": len(resp.content),
        }
        if resp.status_code == 200 and resp.content:
            safe = path.replace("/", "__")
            save(f"candidates/{safe}", resp.content)
            if url.endswith(".js"):
                js_urls.add(url)

    for url in CANDIDATE_ABSOLUTE:
        resp = fetch(url)
        if resp is None:
            continue
        report["endpoints"][url] = {  # type: ignore[index]
            "status": resp.status_code,
            "content_type": resp.headers.get("content-type"),
            "length": len(resp.content),
        }
        if resp.status_code == 200 and resp.content:
            safe = re.sub(r"[^A-Za-z0-9]+", "_", url)[:120]
            save(f"candidates/{safe}", resp.content)

    # Download JS bundles and grep them for URLs / asset paths.
    found_urls: set[str] = set()
    found_paths: set[str] = set()
    for url in sorted(js_urls):
        resp = fetch(url)
        if resp is None or resp.status_code != 200:
            continue
        name = url.rsplit("/", 1)[-1] or "bundle.js"
        save(f"js/{name}", resp.content)
        body = resp.text
        for m in URL_RE.findall(body):
            found_urls.add(m)
        for m in PATH_RE.findall(body):
            found_paths.add(m)

    report["discovered_in_html"] = sorted(discovered)
    report["urls_in_js"] = sorted(found_urls)
    report["paths_in_js"] = sorted(found_paths)

    (OUT / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print("\n==== URLs found in JS ====")
    for u in sorted(found_urls):
        print(u)
    print("\n==== asset/json paths found in JS ====")
    for p in sorted(found_paths):
        print(p)

    return 0


if __name__ == "__main__":
    sys.exit(main())
