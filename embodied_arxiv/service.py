from __future__ import annotations

import json
import os
import re
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

from embodied_arxiv.arxiv_client import ArxivClient
from embodied_arxiv.awards import AwardCatalog
from embodied_arxiv.classifier import classify, core_evidence, normalize_text
from embodied_arxiv.conferences import SUPPORTED_CONFERENCES, detect_conferences
from embodied_arxiv.dblp import DblpClient
from embodied_arxiv.journals import SUPPORTED_JOURNALS
from embodied_arxiv.openalex import OpenAlexClient


ROBOTICS_CONFERENCES = {"CoRL", "ICRA", "RSS", "IROS"}
SORT_KEYS = {
    "date_desc": lambda paper: (paper.get("published_ts", 0), paper.get("title", "")),
    "date_asc": lambda paper: (paper.get("published_ts", 0), paper.get("title", "")),
    "citations_desc": lambda paper: (
        paper.get("cited_by_count", 0),
        paper.get("published_ts", 0),
    ),
    "citations_asc": lambda paper: (
        paper.get("cited_by_count", 0),
        paper.get("published_ts", 0),
    ),
}


class PaperService:
    def __init__(
        self,
        cache_path: str,
        days: int = 15,
        max_results: int = 300,
        openalex_email: str = "",
        openalex_api_key: str = "",
        conference_max_results: int = 200,
        conference_years: int = 5,
        conference_refresh_hours: int = 168,
        journal_max_results: int = 200,
        journal_years: int = 5,
        journal_refresh_hours: int = 168,
        awards_path: str = "data/awards.json",
    ):
        self.cache_path = Path(cache_path)
        self.days = days
        self.arxiv = ArxivClient(max_results=max_results)
        self.openalex = OpenAlexClient(
            email=openalex_email,
            api_key=openalex_api_key,
            conference_max_results=conference_max_results,
            conference_years=conference_years,
            journal_max_results=journal_max_results,
            journal_years=journal_years,
        )
        self.dblp = DblpClient(
            max_results=conference_max_results,
            years=conference_years,
        )
        self.conference_refresh_hours = max(conference_refresh_hours, 1)
        self.journal_refresh_hours = max(journal_refresh_hours, 1)
        self.awards = AwardCatalog(awards_path)
        self._lock = threading.Lock()
        self._refreshing = False
        self._last_error = ""

    def list_papers(
        self,
        category: str = "",
        conference: str = "",
        source: str = "",
        keyword: str = "",
        sort: str = "date_desc",
        from_year: int | None = None,
        to_year: int | None = None,
        min_citations: int | None = None,
        max_citations: int | None = None,
    ) -> dict:
        data = self._read_cache()
        arxiv_papers, conference_papers, journal_papers = self._collections(data)
        arxiv_papers = self._prepare_arxiv(self._recent(arxiv_papers))
        conference_papers = self.awards.apply(self._prepare_conferences(conference_papers))
        journal_papers = self._prepare_journals(journal_papers)
        all_papers = arxiv_papers + conference_papers + journal_papers
        papers = list(all_papers)

        selected_source = source or conference
        if selected_source == "arxiv":
            papers = arxiv_papers
        elif selected_source == "awards":
            papers = [paper for paper in conference_papers if paper.get("awards")]
        elif selected_source == "conference":
            papers = conference_papers
        elif selected_source == "journal":
            papers = journal_papers
        elif selected_source in SUPPORTED_CONFERENCES:
            papers = [
                paper
                for paper in conference_papers
                if paper.get("conference") == selected_source
            ]
        elif selected_source in SUPPORTED_JOURNALS:
            papers = [
                paper
                for paper in journal_papers
                if paper.get("journal") == selected_source
            ]

        if category:
            papers = [
                paper
                for paper in papers
                if category in paper.get("embodied_categories", [])
            ]
        if from_year is not None:
            papers = [
                paper
                for paper in papers
                if (paper.get("publication_year") or 0) >= from_year
            ]
        if to_year is not None:
            papers = [
                paper
                for paper in papers
                if (paper.get("publication_year") or 0) <= to_year
            ]
        if min_citations is not None:
            papers = [
                paper
                for paper in papers
                if paper.get("cited_by_count", 0) >= min_citations
            ]
        if max_citations is not None:
            papers = [
                paper
                for paper in papers
                if paper.get("cited_by_count", 0) <= max_citations
            ]
        if keyword:
            needle = normalize_text(keyword)
            papers = [
                paper
                for paper in papers
                if needle in normalize_text(self._searchable_text(paper))
            ]

        sort = sort if sort in SORT_KEYS else "date_desc"
        papers.sort(
            key=SORT_KEYS[sort],
            reverse=sort in {"date_desc", "citations_desc"},
        )
        categories = sorted(
            {
                category_name
                for paper in all_papers
                for category_name in paper.get("embodied_categories", [])
            }
        )
        years = sorted(
            {
                paper.get("publication_year")
                for paper in conference_papers + journal_papers
                if paper.get("publication_year")
            },
            reverse=True,
        )
        section_counts = {
            "arxiv": len(arxiv_papers),
            "conference": len(conference_papers),
            "journal": len(journal_papers),
            **{
                name: sum(
                    paper.get("conference") == name for paper in conference_papers
                )
                for name in SUPPORTED_CONFERENCES
            },
            **{
                name: sum(
                    paper.get("journal") == name for paper in journal_papers
                )
                for name in SUPPORTED_JOURNALS
            },
            "awards": sum(bool(paper.get("awards")) for paper in conference_papers),
        }
        return {
            "papers": papers,
            "categories": categories,
            "conferences": list(SUPPORTED_CONFERENCES),
            "journals": list(SUPPORTED_JOURNALS),
            "section_counts": section_counts,
            "years": years,
            "count": len(papers),
            "total_count": len(all_papers),
            "days": self.days,
            "updated_at": data.get("updated_at", ""),
            "refreshing": self._refreshing,
            "last_error": self._last_error,
        }

    def status(self) -> dict:
        data = self._read_cache()
        arxiv_papers, conference_papers, journal_papers = self._collections(data)
        return {
            "refreshing": self._refreshing,
            "updated_at": data.get("updated_at", ""),
            "count": (
                len(self._recent(arxiv_papers)) + len(conference_papers) + len(journal_papers)
            ),
            "last_error": self._last_error,
        }

    def start_refresh(self) -> bool:
        with self._lock:
            if self._refreshing:
                return False
            self._refreshing = True
        threading.Thread(target=self._refresh_worker, daemon=True).start()
        return True

    def refresh(self) -> None:
        with self._lock:
            if self._refreshing:
                return
            self._refreshing = True
        self._refresh_worker()

    def _refresh_worker(self) -> None:
        errors = []
        try:
            cached = self._read_cache()
            now = datetime.now(timezone.utc)
            old_arxiv, old_conferences, old_journals = self._collections(cached)
            old_arxiv_by_id = {paper["id"]: paper for paper in old_arxiv}
            conference_updated_at = dict(cached.get("conference_updated_at") or {})
            conference_checked_at = dict(cached.get("conference_checked_at") or {})
            journal_updated_at = dict(cached.get("journal_updated_at") or {})
            journal_checked_at = dict(cached.get("journal_checked_at") or {})

            try:
                arxiv_papers = self._refresh_arxiv(old_arxiv_by_id)
            except Exception as exc:
                arxiv_papers = old_arxiv
                errors.append(f"arXiv: {_short_error(exc)}")

            conference_papers = list(old_conferences)
            for conference in SUPPORTED_CONFERENCES:
                cached_for_conference = [
                    paper
                    for paper in old_conferences
                    if paper.get("conference") == conference
                ]
                if (
                    cached_for_conference
                    and conference not in conference_checked_at
                    and cached.get("updated_at")
                ):
                    conference_checked_at[conference] = cached["updated_at"]
                if not self._source_refresh_due(
                    conference_checked_at.get(conference, ""),
                    now,
                    self.conference_refresh_hours,
                ):
                    continue

                try:
                    fetched = self._fetch_conference(conference)
                    selected = self._classify_conference_papers(fetched, conference)
                    if not selected:
                        raise RuntimeError("主题筛选后没有符合条件的论文")
                    if any(
                        paper.get("id", "").startswith("dblp:")
                        for paper in selected
                    ):
                        selected = self.openalex.enrich_papers(selected, limit=40)
                    merged = self._deduplicate([*cached_for_conference, *selected])
                    conference_papers = [
                        paper
                        for paper in conference_papers
                        if paper.get("conference") != conference
                    ]
                    conference_papers.extend(merged)
                    conference_updated_at[conference] = now.isoformat()
                    conference_checked_at[conference] = now.isoformat()
                except Exception as exc:
                    conference_checked_at[conference] = now.isoformat()
                    errors.append(f"{conference}: {_short_error(exc)}")

            journal_papers = list(old_journals)
            for journal in SUPPORTED_JOURNALS:
                cached_for_journal = [
                    paper
                    for paper in old_journals
                    if paper.get("journal") == journal
                ]
                if (
                    cached_for_journal
                    and journal not in journal_checked_at
                    and cached.get("updated_at")
                ):
                    journal_checked_at[journal] = cached["updated_at"]
                if not self._source_refresh_due(
                    journal_checked_at.get(journal, ""),
                    now,
                    self.journal_refresh_hours,
                ):
                    continue

                try:
                    fetched = self.openalex.journal_papers(journal)
                    selected = self._classify_journal_papers(fetched, journal)
                    if not selected:
                        raise RuntimeError("主题筛选后没有符合条件的论文")
                    merged = self._deduplicate([*cached_for_journal, *selected])
                    journal_papers = [
                        paper
                        for paper in journal_papers
                        if paper.get("journal") != journal
                    ]
                    journal_papers.extend(merged)
                    journal_updated_at[journal] = now.isoformat()
                    journal_checked_at[journal] = now.isoformat()
                except Exception as exc:
                    journal_checked_at[journal] = now.isoformat()
                    errors.append(f"{journal}: {_short_error(exc)}")

            self._write_cache(
                {
                    "updated_at": now.isoformat(),
                    "conference_updated_at": conference_updated_at,
                    "conference_checked_at": conference_checked_at,
                    "journal_updated_at": journal_updated_at,
                    "journal_checked_at": journal_checked_at,
                    "arxiv_papers": arxiv_papers,
                    "conference_papers": self._deduplicate(conference_papers),
                    "journal_papers": self._deduplicate(journal_papers),
                }
            )
            self._last_error = "；".join(errors)
        except Exception as exc:
            self._last_error = _short_error(exc)
        finally:
            with self._lock:
                self._refreshing = False

    def _fetch_conference(self, conference: str) -> list[dict]:
        papers = []
        errors = []
        try:
            papers.extend(self.openalex.conference_papers(conference))
        except Exception as exc:
            errors.append(f"OpenAlex: {_short_error(exc)}")
        try:
            papers.extend(self.dblp.conference_papers(conference))
        except Exception as exc:
            errors.append(f"DBLP: {_short_error(exc)}")
        papers = self._deduplicate(papers)
        papers.sort(
            key=lambda item: (item.get("published_ts", 0), item.get("title", "")),
            reverse=True,
        )
        if not papers:
            detail = "；".join(errors) or "未返回错误详情"
            raise RuntimeError(f"OpenAlex 与 DBLP 均未返回数据；{detail}")
        return papers

    @staticmethod
    def _source_refresh_due(
        value: str,
        now: datetime,
        refresh_hours: int,
    ) -> bool:
        if not value:
            return True
        try:
            last_refresh = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if last_refresh.tzinfo is None:
                last_refresh = last_refresh.replace(tzinfo=timezone.utc)
        except (AttributeError, TypeError, ValueError):
            return True
        return now - last_refresh >= timedelta(
            hours=refresh_hours,
        )

    def _refresh_arxiv(self, existing: dict[str, dict]) -> list[dict]:
        selected = []
        for paper in self._recent(self.arxiv.fetch()):
            categories, evidence = classify(paper["title"], paper["summary"])
            if not categories:
                continue
            paper["source_kind"] = "arxiv"
            paper["conference"] = ""
            paper["conferences"] = detect_conferences(
                paper.get("comment", ""),
                paper.get("journal_ref", ""),
            )
            paper["publication_year"] = self._paper_year(paper)
            paper["cited_by_count"] = existing.get(paper["id"], {}).get(
                "cited_by_count",
                0,
            )
            paper["awards"] = []
            paper["embodied_categories"] = categories
            paper["match_evidence"] = evidence
            old = existing.get(paper["id"], {})
            paper["institutions"] = old.get("institutions", [])
            paper["institutions_source"] = old.get("institutions_source", "")
            selected.append(paper)

        for paper in [item for item in selected if not item["institutions"]][:30]:
            try:
                institutions = self.openalex.institutions_for(paper["title"])
                if institutions:
                    paper["institutions"] = institutions
                    paper["institutions_source"] = "OpenAlex"
            except Exception:
                continue
        selected.sort(key=lambda item: item["published_ts"], reverse=True)
        return selected

    @staticmethod
    def _classify_conference_papers(
        papers: list[dict],
        conference: str,
    ) -> list[dict]:
        selected = []
        for paper in papers:
            categories, evidence = classify(
                paper.get("title", ""),
                paper.get("summary", ""),
            )
            if not categories:
                core = core_evidence(
                    paper.get("title", ""),
                    paper.get("summary", ""),
                )
                if conference not in ROBOTICS_CONFERENCES and not core:
                    continue
                categories = ["机器人学习"]
                evidence = core or [conference]
            paper["embodied_categories"] = categories
            paper["match_evidence"] = evidence
            selected.append(paper)
        return selected

    @staticmethod
    def _classify_journal_papers(
        papers: list[dict],
        journal: str,
    ) -> list[dict]:
        return PaperService._classify_robotics_source_papers(papers, journal)

    @staticmethod
    def _classify_robotics_source_papers(papers: list[dict], source: str) -> list[dict]:
        selected = []
        for paper in papers:
            categories, evidence = classify(
                paper.get("title", ""),
                paper.get("summary", ""),
            )
            if not categories:
                categories = ["机器人学习"]
                evidence = core_evidence(
                    paper.get("title", ""),
                    paper.get("summary", ""),
                ) or [source]
            paper["embodied_categories"] = categories
            paper["match_evidence"] = evidence
            selected.append(paper)
        return selected

    def _recent(self, papers: list[dict]) -> list[dict]:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=self.days)).timestamp()
        return [paper for paper in papers if paper.get("published_ts", 0) >= cutoff]

    @classmethod
    def _prepare_arxiv(cls, papers: list[dict]) -> list[dict]:
        prepared = []
        for paper in papers:
            item = dict(paper)
            item["source_kind"] = "arxiv"
            item["conference"] = ""
            item["conferences"] = item.get("conferences") or detect_conferences(
                item.get("comment", ""),
                item.get("journal_ref", ""),
            )
            item["publication_year"] = item.get("publication_year") or cls._paper_year(item)
            item["cited_by_count"] = int(item.get("cited_by_count") or 0)
            item["awards"] = item.get("awards") or []
            prepared.append(item)
        return prepared

    @staticmethod
    def _prepare_conferences(papers: list[dict]) -> list[dict]:
        prepared = []
        for paper in papers:
            item = dict(paper)
            conference = item.get("conference", "")
            item["source_kind"] = "conference"
            item["conferences"] = [conference] if conference else []
            item["cited_by_count"] = int(item.get("cited_by_count") or 0)
            item["awards"] = item.get("awards") or []
            prepared.append(item)
        return prepared

    @staticmethod
    def _prepare_journals(papers: list[dict]) -> list[dict]:
        prepared = []
        for paper in papers:
            item = dict(paper)
            item["source_kind"] = "journal"
            item["conference"] = ""
            item["conferences"] = []
            item["cited_by_count"] = int(item.get("cited_by_count") or 0)
            item["awards"] = item.get("awards") or []
            prepared.append(item)
        return prepared

    @staticmethod
    def _collections(data: dict) -> tuple[list[dict], list[dict], list[dict]]:
        if any(
            key in data
            for key in ("arxiv_papers", "conference_papers", "journal_papers")
        ):
            return (
                data.get("arxiv_papers", []),
                data.get("conference_papers", []),
                data.get("journal_papers", []),
            )
        return data.get("papers", []), [], []

    @staticmethod
    def _paper_year(paper: dict) -> int | None:
        published = paper.get("published", "")
        try:
            return int(published[:4])
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _searchable_text(paper: dict) -> str:
        return " ".join(
            [
                paper.get("title", ""),
                paper.get("summary", ""),
                " ".join(paper.get("authors", [])),
                " ".join(paper.get("institutions", [])),
                paper.get("conference", ""),
                paper.get("journal", ""),
                " ".join(
                    award.get("award", "")
                    for award in paper.get("awards", [])
                ),
            ]
        )

    @staticmethod
    def _deduplicate(papers: list[dict]) -> list[dict]:
        result = {}
        for paper in papers:
            identity = paper.get("doi") or normalize_text(paper.get("title", ""))
            if not identity:
                continue
            source_name = paper.get("conference") or paper.get("journal") or ""
            key = (
                paper.get("source_kind", ""),
                source_name,
                identity,
            )
            existing = result.get(key)
            if not existing or _paper_quality(paper) >= _paper_quality(existing):
                result[key] = paper
        return list(result.values())

    def _read_cache(self) -> dict:
        if not self.cache_path.exists():
            return {"updated_at": "", "arxiv_papers": [], "conference_papers": []}
        try:
            return json.loads(self.cache_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"updated_at": "", "arxiv_papers": [], "conference_papers": []}

    def _write_cache(self, data: dict) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.cache_path.with_suffix(".tmp")
        temp_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(temp_path, self.cache_path)


def _short_error(exc: Exception) -> str:
    if isinstance(exc, requests.HTTPError):
        response = getattr(exc, "response", None)
        if response is not None:
            return f"HTTP {response.status_code}"
    if isinstance(exc, requests.Timeout):
        return "request timed out"
    if isinstance(exc, requests.ConnectionError):
        message = str(exc).lower()
        if "reset" in message:
            return "connection reset"
        return "connection failed"

    message = re.sub(r"\s+for url:.*$", "", str(exc), flags=re.DOTALL).strip()
    return (message or exc.__class__.__name__)[:180]


def _paper_quality(paper: dict) -> tuple[int, int, int, int]:
    return (
        1 if paper.get("openalex_id") else 0,
        1 if paper.get("summary") else 0,
        1 if paper.get("institutions") else 0,
        int(paper.get("cited_by_count") or 0),
    )
