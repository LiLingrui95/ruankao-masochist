"""Verify every catalogued source URL without copying source content."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests


ROOT = Path(__file__).parent


def check(url: str) -> dict[str, object]:
    try:
        response = requests.get(url, timeout=25, allow_redirects=True)
        return {
            "url": url,
            "status_code": response.status_code,
            "reachable": response.status_code < 400,
            "final_url": response.url,
            "content_type": response.headers.get("content-type", ""),
            "content_length": len(response.content),
            "checked_on": "2026-09-24",
        }
    except requests.RequestException as exc:
        return {
            "url": url,
            "status_code": None,
            "reachable": False,
            "error": type(exc).__name__,
            "checked_on": "2026-09-24",
        }


def main() -> None:
    coverage = json.loads((ROOT / "coverage.json").read_text(encoding="utf-8"))
    urls = sorted({url for entry in coverage["entries"] for url in entry["source_urls"]})
    with ThreadPoolExecutor(max_workers=8) as pool:
        checks = list(pool.map(check, urls))
    report = {
        "as_of": "2026-09-24",
        "method": "HTTP GET with redirects; response body was not retained",
        "unique_urls": len(checks),
        "reachable": sum(bool(item["reachable"]) for item in checks),
        "checks": checks,
    }
    (ROOT / "link-check.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({key: report[key] for key in ("unique_urls", "reachable")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
