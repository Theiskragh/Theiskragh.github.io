import json
import argparse
import time
from datetime import date

import requests

SEMANTIC_SCHOLAR_BASE = "https://api.semanticscholar.org/graph/v1"
AUTHOR_SEARCH_NAME = "Theis Kragh"
HEADERS = {"User-Agent": "fetch_scholar/1.0 (academic-profile-site; contact via GitHub)"}
TIMEOUT = 30
MAX_RETRIES = 3


def _get(url, params=None):
    """GET with retry logic (3 retries, exponential backoff)."""
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(url, params=params, headers=HEADERS, timeout=TIMEOUT)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            if attempt < MAX_RETRIES - 1:
                wait = 2 ** attempt
                print(f"Request failed ({e}), retrying in {wait}s…")
                time.sleep(wait)
            else:
                raise RuntimeError(f"Request failed after {MAX_RETRIES} attempts: {e}") from e


def find_author_id(name):
    """Search Semantic Scholar for an author by name and return the best match's authorId."""
    data = _get(
        f"{SEMANTIC_SCHOLAR_BASE}/author/search",
        params={"query": name, "fields": "name,affiliations,paperCount"},
    )
    results = data.get("data", [])
    if not results:
        raise RuntimeError(f"No Semantic Scholar author found for '{name}'")
    author = results[0]
    print(f"Found author: {author.get('name')} (ID: {author.get('authorId')})")
    return author["authorId"]


def _paper_url(paper):
    """Return the best available URL for a paper: DOI link > Semantic Scholar page > ''."""
    doi = (paper.get("externalIds") or {}).get("DOI")
    if doi:
        return f"https://doi.org/{doi}"
    paper_id = paper.get("paperId", "")
    return f"https://www.semanticscholar.org/paper/{paper_id}" if paper_id else ""


def fetch_publications(author_id, max_pubs=None):
    """Fetch all papers for a Semantic Scholar author ID, with pagination."""
    papers = []
    offset = 0
    limit = 100
    fields = "title,authors,year,venue,citationCount,externalIds,openAccessPdf"

    while True:
        data = _get(
            f"{SEMANTIC_SCHOLAR_BASE}/author/{author_id}/papers",
            params={"fields": fields, "limit": limit, "offset": offset},
        )
        batch = data.get("data", [])
        papers.extend(batch)

        if max_pubs and len(papers) >= max_pubs:
            papers = papers[:max_pubs]
            break

        if len(batch) < limit:
            break

        offset += limit
        time.sleep(1)

    publications = []
    for paper in papers:
        scholar_url = _paper_url(paper)

        open_access = paper.get("openAccessPdf") or {}
        pdf_url = open_access.get("url", "")

        authors_list = paper.get("authors") or []
        authors_str = ", ".join(a.get("name", "") for a in authors_list)

        year_raw = paper.get("year")
        year = int(year_raw) if year_raw is not None else None

        entry = {
            "title": paper.get("title", ""),
            "authors": authors_str,
            "year": year,
            "venue": paper.get("venue") or "",
            "citations": paper.get("citationCount", 0),
            "scholar_url": scholar_url,
            "pdf_url": pdf_url,
        }
        publications.append(entry)

    # Sort by year descending, unknown years last
    publications.sort(key=lambda p: p["year"] if p["year"] is not None else -1, reverse=True)
    return publications


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch publications from Semantic Scholar")
    parser.add_argument(
        "--scholar-id",
        dest="scholar_id",
        default=None,
        help=(
            "Semantic Scholar author ID. If omitted, the author is looked up by name "
            f"'{AUTHOR_SEARCH_NAME}'."
        ),
    )
    parser.add_argument(
        "--max-pubs",
        type=int,
        help="Maximum number of publications to fetch",
    )
    parser.add_argument(
        "--output",
        default="data/papers.json",
        help="Path to output JSON file (default: %(default)s)",
    )
    args = parser.parse_args()

    author_id = args.scholar_id or find_author_id(AUTHOR_SEARCH_NAME)

    publications = fetch_publications(author_id, args.max_pubs)

    output = {
        "scholar_id": author_id,
        "updated": date.today().isoformat(),
        "papers": publications,
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"Saved {len(publications)} publications to {args.output}")
