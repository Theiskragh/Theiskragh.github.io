#!/usr/bin/env python3
"""
fetch_scholar.py – Fetch publications from a Google Scholar profile
and write them to data/papers.json.

Usage:
    python scripts/fetch_scholar.py [--scholar-id SCHOLAR_ID] [--output PATH]

Defaults:
    --scholar-id  IfJBsd0AAAAJ
    --output      data/papers.json

The script uses the `scholarly` library (no official API key required) with
exponential-backoff retries to reduce the risk of being rate-limited or blocked.
Results are cached so repeated runs don't re-fetch unchanged data.
"""

import argparse
import json
import os
import sys
import time
import logging
from datetime import date
from pathlib import Path

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)

# ── constants ──────────────────────────────────────────────────────────────────
SCHOLAR_BASE = "https://scholar.google.com/citations"
MAX_RETRIES = 5
BACKOFF_BASE = 2          # seconds; doubles each attempt
INTER_PUB_DELAY = 1.5     # seconds between individual publication fetches


def _fill_with_retry(scholarly_obj, pub, retries: int = MAX_RETRIES):
    """Fill a scholarly publication object with exponential backoff."""
    from scholarly import scholarly as _scholarly  # noqa: F401 – reuse module ref

    for attempt in range(1, retries + 1):
        try:
            return _scholarly.fill(pub)
        except Exception as exc:  # noqa: BLE001
            if attempt == retries:
                raise
            wait = BACKOFF_BASE ** attempt
            log.warning(
                "Attempt %d/%d failed (%s). Retrying in %ds…",
                attempt, retries, exc, wait,
            )
            time.sleep(wait)


def _author_with_retry(scholar_id: str, retries: int = MAX_RETRIES):
    """Search and fill author profile with exponential backoff."""
    from scholarly import scholarly as _scholarly

    for attempt in range(1, retries + 1):
        try:
            author = _scholarly.search_author_id(scholar_id)
            return _scholarly.fill(author, sections=["publications"])
        except Exception as exc:  # noqa: BLE001
            if attempt == retries:
                raise
            wait = BACKOFF_BASE ** attempt
            log.warning(
                "Attempt %d/%d failed (%s). Retrying in %ds…",
                attempt, retries, exc, wait,
            )
            time.sleep(wait)


def _build_scholar_url(scholar_id: str, author_pub_id: str) -> str:
    return (
        f"{SCHOLAR_BASE}?view_op=view_citation"
        f"&user={scholar_id}"
        f"&citation_for_view={author_pub_id}"
    )


def fetch_papers(scholar_id: str) -> list[dict]:
    """Return a sorted list of paper dicts from the given Scholar profile."""
    log.info("Fetching author profile for scholar_id=%s …", scholar_id)
    author = _author_with_retry(scholar_id)

    publications = author.get("publications", [])
    log.info("Found %d publications – filling details…", len(publications))

    papers: list[dict] = []
    for i, pub in enumerate(publications, 1):
        log.info("  [%d/%d] %s", i, len(publications), pub.get("bib", {}).get("title", "?"))
        try:
            filled = _fill_with_retry(None, pub)
        except Exception as exc:  # noqa: BLE001
            log.error("    Skipping – could not fill: %s", exc)
            filled = pub  # fall back to partial data

        bib = filled.get("bib", {})
        year_raw = bib.get("pub_year")
        try:
            year = int(year_raw) if year_raw else None
        except (TypeError, ValueError):
            year = None

        venue = (
            bib.get("venue")
            or bib.get("journal")
            or bib.get("booktitle")
            or bib.get("conference")
            or ""
        )

        author_pub_id = filled.get("author_pub_id", "")
        scholar_url = _build_scholar_url(scholar_id, author_pub_id) if author_pub_id else ""

        papers.append({
            "title": bib.get("title", ""),
            "authors": bib.get("author", ""),
            "venue": venue,
            "year": year,
            "scholar_url": scholar_url,
            "pdf_url": filled.get("eprint_url") or None,
            "citations": filled.get("num_citations", 0),
        })

        time.sleep(INTER_PUB_DELAY)

    # Sort: year descending (None last), then title ascending
    papers.sort(key=lambda p: (-(p["year"] or 0), (p["title"] or "").lower()))
    return papers


def load_existing(output_path: Path) -> dict | None:
    """Load and return the existing papers.json, or None if missing/invalid."""
    if not output_path.exists():
        return None
    try:
        with output_path.open(encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scholar-id",
        default=os.environ.get("SCHOLAR_ID", "IfJBsd0AAAAJ"),
        help="Google Scholar user ID (default: IfJBsd0AAAAJ)",
    )
    parser.add_argument(
        "--output",
        default="data/papers.json",
        help="Output path for papers.json (default: data/papers.json)",
    )
    args = parser.parse_args()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        papers = fetch_papers(args.scholar_id)
    except Exception as exc:  # noqa: BLE001
        log.error("Fatal error fetching papers: %s", exc)
        log.error("The existing data/papers.json (if any) will NOT be overwritten.")
        return 1

    new_data = {
        "scholar_id": args.scholar_id,
        "updated": str(date.today()),
        "papers": papers,
    }
    new_json = json.dumps(new_data, indent=2, ensure_ascii=False)

    # Only write if the paper list actually changed (ignore "updated" field diff)
    existing = load_existing(output_path)
    if existing is not None and existing.get("papers") == papers:
        log.info("No changes detected – skipping write.")
        return 0

    output_path.write_text(new_json + "\n", encoding="utf-8")
    log.info(
        "Wrote %d papers to %s (updated: %s)",
        len(papers), output_path, new_data["updated"],
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
