from __future__ import annotations

from datetime import datetime, timezone

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
        response = requests.get(
            self.endpoint,
            params={
                "q": f"stream:{DBLP_STREAMS[conference]}:",
                "h": self.max_results,
                "format": "json",
            },
            timeout=self.timeout,
            headers={"User-Agent": "EmbodiedArxivRadar/2.0"},
        )
        response.raise_for_status()
        cutoff_year = datetime.now(timezone.utc).year - self.years + 1
        hits = response.json().get("result", {}).get("hits", {}).get("hit", [])
        papers = [
            _parse_hit(hit.get("info", {}), conference)
            for hit in hits
            if _year(hit.get("info", {}).get("year")) >= cutoff_year
        ]
        return [paper for paper in papers if paper["title"]]


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
