import json
import argparse
from datetime import date
from scholarly import scholarly


DEFAULT_SCHOLAR_ID = "IfJBsd0AAAAJ"


def fetch_publications(scholar_id, max_pubs=None):
    """Fetch publications for a Google Scholar author ID using the scholarly library."""
    try:
        author = scholarly.search_author_id(scholar_id)
        author = scholarly.fill(author, sections=["publications"])
    except Exception as e:
        raise RuntimeError(f"Failed to fetch author profile for '{scholar_id}': {e}") from e

    pubs = author.get("publications", [])
    if max_pubs:
        pubs = pubs[:max_pubs]

    publications = []
    for pub in pubs:
        filled = scholarly.fill(pub)
        bib = filled.get("bib", {})

        year_raw = bib.get("pub_year")
        year = int(year_raw) if year_raw and str(year_raw).isdigit() else None

        venue = (
            bib.get("venue")
            or bib.get("journal")
            or bib.get("booktitle")
            or ""
        )

        entry = {
            "title": bib.get("title", ""),
            "authors": bib.get("author", ""),
            "year": year,
            "venue": venue,
            "citations": filled.get("num_citations", 0),
            "scholar_url": filled.get("pub_url", ""),
            "pdf_url": filled.get("eprint_url", ""),
        }
        publications.append(entry)

    # Sort by year descending, unknown years last
    publications.sort(key=lambda p: p["year"] if p["year"] is not None else -1, reverse=True)
    return publications


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch publications from Google Scholar")
    parser.add_argument(
        "--scholar-id",
        dest="scholar_id",
        default=DEFAULT_SCHOLAR_ID,
        help="Google Scholar author ID (default: %(default)s)",
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

    publications = fetch_publications(args.scholar_id, args.max_pubs)

    output = {
        "scholar_id": args.scholar_id,
        "updated": date.today().isoformat(),
        "papers": publications,
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"Saved {len(publications)} publications to {args.output}")
