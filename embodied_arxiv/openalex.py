from __future__ import annotations

import re
from datetime import date, datetime, timezone
from difflib import SequenceMatcher
from math import ceil

import requests

from embodied_arxiv.conferences import CONFERENCES


class OpenAlexClient:
    works_endpoint = "https://api.openalex.org/works"
    sources_endpoint = "https://api.openalex.org/sources"

    def __init__(
        self,
        email: str = "",
        api_key: str = "",
        timeout: int = 30,
        conference_max_results: int = 200,
        conference_years: int = 5,
    ):
        self.email = email
        self.api_key = api_key
        self.timeout = timeout
        self.conference_max_results = min(max(conference_max_results, 1), 1000)
        self.conference_years = max(conference_years, 1)

    def institutions_for(self, title: str) -> list[str]:
        response = self._get(
            self.works_endpoint,
            {"search": title, "per-page": 3, "select": "title,authorships"},
        )
        normalized = _normalize(title)
        for work in response.get("results", []):
            candidate = _normalize(work.get("title", ""))
            if SequenceMatcher(None, normalized, candidate).ratio() < 0.9:
                continue
            return _institutions(work)
        return []

    def conference_papers(self, conference: str) -> list[dict]:
        years = list(range(date.today().year, date.today().year - self.conference_years, -1))
        source_ids = self._source_ids(conference, years)
        if not source_ids:
            raise RuntimeError(f"OpenAlex 未找到 {conference} 的会议来源")
        papers = []
        per_year_limit = max(1, ceil(self.conference_max_results / len(years)))
        for year in years:
            cursor = "*"
            year_count = 0
            filters = [
                f"primary_location.source.id:{'|'.join(source_ids)}",
                f"from_publication_date:{year}-01-01",
                f"to_publication_date:{year}-12-31",
            ]
            while (
                len(papers) < self.conference_max_results
                and year_count < per_year_limit
                and cursor
            ):
                page_size = min(
                    200,
                    self.conference_max_results - len(papers),
                    per_year_limit - year_count,
                )
                data = self._get(
                    self.works_endpoint,
                    {
                        "filter": ",".join(filters),
                        "per-page": page_size,
                        "sort": "publication_date:desc",
                        "cursor": cursor,
                        "select": (
                            "id,doi,title,display_name,publication_date,publication_year,"
                            "cited_by_count,authorships,primary_location,"
                            "abstract_inverted_index,ids"
                        ),
                    },
                )
                results = data.get("results", [])
                papers.extend(
                    self._parse_work(work, conference)
                    for work in results
                    if work.get("title")
                )
                year_count += len(results)
                cursor = data.get("meta", {}).get("next_cursor")
                if not results:
                    break
            if len(papers) >= self.conference_max_results:
                break
        papers = self._deduplicate(papers)
        papers.sort(
            key=lambda item: (item.get("published_ts", 0), item.get("title", "")),
            reverse=True,
        )
        if not papers:
            raise RuntimeError(f"OpenAlex 未返回 {conference} 会议论文")
        return papers[: self.conference_max_results]

    def enrich_papers(self, papers: list[dict], limit: int = 100) -> list[dict]:
        enriched = []
        for index, paper in enumerate(papers):
            item = dict(paper)
            if index >= limit:
                enriched.append(item)
                continue
            try:
                match = self._work_for_title(item.get("title", ""))
            except Exception:
                match = None
            if match:
                item.update(
                    {
                        "summary": _abstract(match.get("abstract_inverted_index"))
                        or item.get("summary", ""),
                        "cited_by_count": int(match.get("cited_by_count") or 0),
                        "institutions": _institutions(match)
                        or item.get("institutions", []),
                        "institutions_source": "OpenAlex",
                    }
                )
            enriched.append(item)
        return enriched

    def _work_for_title(self, title: str) -> dict | None:
        if not title:
            return None
        data = self._get(
            self.works_endpoint,
            {
                "search": title,
                "per-page": 3,
                "select": (
                    "title,display_name,cited_by_count,authorships,"
                    "abstract_inverted_index"
                ),
            },
        )
        normalized = _normalize(title)
        for work in data.get("results", []):
            candidate = _normalize(work.get("display_name") or work.get("title", ""))
            if SequenceMatcher(None, normalized, candidate).ratio() >= 0.92:
                return work
        return None

    def _source_ids(self, conference: str, years: list[int] | None = None) -> list[str]:
        config = CONFERENCES[conference]
        aliases = [_normalize(alias) for alias in config["aliases"]]
        source_ids = []
        base_queries = list(dict.fromkeys((config["name"], *config["aliases"])))
        year_queries = []
        for year in years or []:
            for query in base_queries:
                year_queries.extend((f"{query} {year}", f"{year} {query}"))
        queries = list(dict.fromkeys([*year_queries, *base_queries]))
        for query in queries:
            data = self._get(
                self.sources_endpoint,
                {
                    "search": query,
                    "per-page": 25,
                    "select": "id,display_name,type",
                },
            )
            for source in data.get("results", []):
                display_name = _normalize(source.get("display_name", ""))
                if not display_name or not _source_matches(display_name, aliases):
                    continue
                source_id = source.get("id", "").rsplit("/", 1)[-1]
                if source_id:
                    source_ids.append(source_id)
        return list(dict.fromkeys(source_ids))[:50]

    def _get(self, url: str, params: dict) -> dict:
        params = dict(params)
        if self.email:
            params["mailto"] = self.email
        if self.api_key:
            params["api_key"] = self.api_key
        response = requests.get(
            url,
            params=params,
            timeout=self.timeout,
            headers={"User-Agent": "EmbodiedArxivRadar/2.0"},
        )
        response.raise_for_status()
        return response.json()

    @staticmethod
    def _parse_work(work: dict, conference: str) -> dict:
        publication_date = work.get("publication_date") or ""
        location = work.get("primary_location") or {}
        source = location.get("source") or {}
        authors = [
            authorship.get("author", {}).get("display_name", "")
            for authorship in work.get("authorships", [])
            if authorship.get("author", {}).get("display_name")
        ]
        doi = (work.get("doi") or "").removeprefix("https://doi.org/")
        openalex_id = work.get("id", "").rsplit("/", 1)[-1]
        landing_page = location.get("landing_page_url") or work.get("doi") or work.get("id", "")
        pdf_url = location.get("pdf_url") or ""
        arxiv_id = _arxiv_id(work)
        return {
            "id": f"openalex:{openalex_id}",
            "openalex_id": openalex_id,
            "source_kind": "conference",
            "conference": conference,
            "conferences": [conference],
            "venue": source.get("display_name") or CONFERENCES[conference]["name"],
            "title": work.get("display_name") or work.get("title", ""),
            "summary": _abstract(work.get("abstract_inverted_index")),
            "authors": authors,
            "institutions": _institutions(work),
            "institutions_source": "OpenAlex",
            "published": publication_date,
            "published_ts": _date_timestamp(publication_date),
            "publication_year": work.get("publication_year"),
            "cited_by_count": int(work.get("cited_by_count") or 0),
            "doi": doi,
            "doi_url": f"https://doi.org/{doi}" if doi else "",
            "paper_url": landing_page,
            "pdf_url": pdf_url,
            "arxiv_url": f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else "",
            "arxiv_categories": [],
            "primary_category": "",
            "external_urls": [],
            "comment": "",
            "journal_ref": "",
            "awards": [],
        }

    @staticmethod
    def _deduplicate(papers: list[dict]) -> list[dict]:
        result = {}
        for paper in papers:
            key = paper.get("doi") or _normalize(paper.get("title", ""))
            if key:
                result[key] = paper
        return list(result.values())


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _source_matches(display_name: str, aliases: list[str]) -> bool:
    display_tokens = set(display_name.split())
    for alias in aliases:
        if alias == display_name or alias in display_name or display_name in alias:
            return True
        alias_tokens = set(alias.split())
        if len(alias_tokens) >= 4 and len(alias_tokens & display_tokens) / len(alias_tokens) >= 0.75:
            return True
    return False


def _institutions(work: dict) -> list[str]:
    names = []
    for authorship in work.get("authorships", []):
        for institution in authorship.get("institutions", []):
            if institution.get("display_name"):
                names.append(institution["display_name"])
    return list(dict.fromkeys(names))


def _abstract(inverted_index: dict | None) -> str:
    if not inverted_index:
        return ""
    words = [
        (position, word)
        for word, positions in inverted_index.items()
        for position in positions
    ]
    return " ".join(word for _, word in sorted(words))


def _arxiv_id(work: dict) -> str:
    value = (work.get("ids") or {}).get("arxiv", "")
    return value.rsplit("/", 1)[-1] if value else ""


def _date_timestamp(value: str) -> float:
    if not value:
        return 0
    try:
        return datetime.fromisoformat(value).replace(tzinfo=timezone.utc).timestamp()
    except ValueError:
        return 0
