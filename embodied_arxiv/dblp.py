from __future__ import annotations

from datetime import datetime, timezone
from math import ceil

import requests

from embodied_arxiv.conferences import CONFERENCES


DBLP_STREAMS = {
    "CoRL": "conf/corl",
    "ICRA": "conf/icra",
    "RSS": "conf/rss",
    "IROS": "conf/iros",
    "CVPR": "conf/cvpr",
    "ICLR": "conf/iclr",
    "NeurIPS": "conf/nips",
    "ICML": "conf/icml",
    "ICCV": "conf/iccv",
}


class DblpClient:
    endpoint = "https://dblp.org/search/publ/api"

    def __init__(self, timeout: int = 30, max_results: int = 1000, years: int = 5):
        self.timeout = timeout
        self.max_results = min(max(max_results, 1), 1000)
        self.years = max(years, 1)

    def conference_papers(self, conference: str) -> list[dict]:
        cutoff_year = datetime.now(timezone.utc).year - self.years + 1
        per_year_limit = max(1, ceil(self.max_results / self.years))
        page_size = 1000
        max_pages = self.years + 4
        papers = []
        year_counts: dict[int, int] = {}
        for page in range(max_pages):
            response = requests.get(
                self.endpoint,
                params={
                    "q": f"stream:{DBLP_STREAMS[conference]}:",
                    "h": page_size,
                    "f": page * page_size,
                    "format": "json",
                },
                timeout=self.timeout,
                headers={"User-Agent": "EmbodiedArxivRadar/2.0"},
            )
            response.raise_for_status()
            hits = response.json().get("result", {}).get("hits", {}).get("hit", [])
            if not hits:
                break
            for hit in hits:
                info = hit.get("info", {})
                year = _year(info.get("year"))
                if year < cutoff_year:
                    continue
                if year_counts.get(year, 0) >= per_year_limit:
                    continue
                paper = _parse_hit(info, conference)
                if not paper["title"]:
                    continue
                papers.append(paper)
                year_counts[year] = year_counts.get(year, 0) + 1
                if len(papers) >= self.max_results:
                    break
            if len(papers) >= self.max_results:
                break
        papers.sort(
            key=lambda item: (item.get("published_ts", 0), item.get("title", "")),
            reverse=True,
        )
        return papers[: self.max_results]


def _parse_hit(info: dict, conference: str) -> dict:
    year = _year(info.get("year"))
    authors = info.get("authors", {}).get("author", [])
    if isinstance(authors, dict):
        authors = [authors]
    author_names = [
        author.get("text", "") if isinstance(author, dict) else str(author)
        for author in authors
    ]
    doi = str(info.get("doi") or "").removeprefix("https://doi.org/")
    urls = info.get("ee") or []
    if isinstance(urls, str):
        urls = [urls]
    dblp_url = info.get("url") or ""
    paper_url = urls[0] if urls else (
        f"https://dblp.org/{dblp_url}" if dblp_url else ""
    )
    published = f"{year}-01-01" if year else ""
    return {
        "id": f"dblp:{info.get('key', '')}",
        "dblp_key": info.get("key", ""),
        "source_kind": "conference",
        "conference": conference,
        "conferences": [conference],
        "venue": info.get("venue") or CONFERENCES[conference]["name"],
        "title": str(info.get("title") or "").rstrip("."),
        "summary": "",
        "authors": [name for name in author_names if name],
        "institutions": [],
        "institutions_source": "",
        "published": published,
        "published_ts": _date_timestamp(published),
        "publication_year": year or None,
        "cited_by_count": 0,
        "doi": doi,
        "doi_url": f"https://doi.org/{doi}" if doi else "",
        "paper_url": paper_url,
        "pdf_url": "",
        "arxiv_url": "",
        "arxiv_categories": [],
        "primary_category": "",
        "external_urls": list(dict.fromkeys(urls))[1:5],
        "comment": "",
        "journal_ref": "",
        "awards": [],
    }


def _year(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _date_timestamp(value: str) -> float:
    if not value:
        return 0
    try:
        return datetime.fromisoformat(value).replace(tzinfo=timezone.utc).timestamp()
    except ValueError:
        return 0
