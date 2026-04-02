# Theiskragh.github.io

Professional academic website hosted at **https://theiskragh.github.io/** with an automatically-updated publications list pulled from Google Scholar.

---

## Table of Contents

- [How the automation works](#how-the-automation-works)
- [Running the fetch script locally](#running-the-fetch-script-locally)
- [Changing the Scholar profile ID](#changing-the-scholar-profile-id)
- [Limitations](#limitations)

---

## How the automation works

A GitHub Actions workflow (`.github/workflows/update-papers.yml`) runs **every Sunday at 02:00 UTC** and on **manual dispatch**:

1. Checks out the repository.
2. Sets up Python 3.11 and installs pinned dependencies from `scripts/requirements.txt`.
3. Runs `scripts/fetch_scholar.py`, which:
   - Fetches the author profile and all publications from Google Scholar using the [`scholarly`](https://pypi.org/project/scholarly/) library.
   - Implements exponential-backoff retries to handle transient rate-limiting.
   - Writes results to `data/papers.json` (sorted by year descending, then title).
   - **Skips the write** if the fetched paper list is identical to the existing one (no unnecessary commits).
4. If `data/papers.json` changed, commits it back with the bot identity `github-actions[bot]` and the message `chore: update papers.json from Google Scholar [skip ci]`.

The static site (`index.html`) loads `data/papers.json` at page load via the Fetch API; **the site works even if the Action fails** because the last committed JSON file is always served by GitHub Pages.

---

## Running the fetch script locally

```bash
# 1. Create and activate a virtual environment (optional but recommended)
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r scripts/requirements.txt

# 3. Run the script (writes to data/papers.json by default)
python scripts/fetch_scholar.py

# Optional: specify a different Scholar ID or output path
python scripts/fetch_scholar.py --scholar-id IfJBsd0AAAAJ --output data/papers.json
```

You can also set the Scholar ID via an environment variable:

```bash
SCHOLAR_ID=IfJBsd0AAAAJ python scripts/fetch_scholar.py
```

---

## Changing the Scholar profile ID

1. **Workflow** – edit `.github/workflows/update-papers.yml` and change the value of `SCHOLAR_ID`:
   ```yaml
   env:
     SCHOLAR_ID: "YOUR_NEW_ID"
   ```
2. **Local runs** – pass `--scholar-id YOUR_NEW_ID` to the script or export `SCHOLAR_ID=YOUR_NEW_ID`.

The Scholar ID is the value of the `user=` parameter in your Google Scholar profile URL:  
`https://scholar.google.com/citations?user=`**`IfJBsd0AAAAJ`**`&hl=en`

---

## Limitations

| Issue | Details |
|---|---|
| **No official API** | Google Scholar has no public API. The site is scraped using `scholarly`, which may break if Google changes its HTML structure. |
| **Rate limiting / blocking** | Google Scholar aggressively rate-limits automated requests. The workflow uses a conservative weekly schedule and per-request delays (`INTER_PUB_DELAY = 1.5 s`) and exponential-backoff retries to reduce risk. |
| **CAPTCHAs** | In some environments (shared CI runners) Scholar may serve CAPTCHAs that `scholarly` cannot solve without a proxy or paid SerpAPI key. The workflow uses `continue-on-error: true` so a blocked fetch does not break the site. |
| **Caching / stale data** | `data/papers.json` is committed to the repository and served by GitHub Pages. The site will display the last successfully fetched data if a scrape fails. |
| **Incomplete metadata** | Venue, PDF links, and citation counts depend on what Scholar exposes for each paper and may not always be available. |
