from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

from embodied_arxiv.arxiv_client import ArxivClient
from embodied_arxiv.awards import AwardCatalog
from embodied_arxiv.classifier import classify, normalize_text
from embodied_arxiv.conferences import SUPPORTED_CONFERENCES, detect_conferences
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
        )
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
        arxiv_papers, conference_papers = self._collections(data)
        arxiv_papers = self._prepare_arxiv(self._recent(arxiv_papers))
        conference_papers = self.awards.apply(self._prepare_conferences(conference_papers))
        all_papers = arxiv_papers + conference_papers
        papers = list(all_papers)

        selected_source = source or conference
        if selected_source == "arxiv":
            papers = arxiv_papers
        elif selected_source == "awards":
            papers = [paper for paper in conference_papers if paper.get("awards")]
        elif selected_source in SUPPORTED_CONFERENCES:
            papers = [
                paper
                for paper in conference_papers
                if paper.get("conference") == selected_source
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
                for paper in conference_papers
                if paper.get("publication_year")
            },
            reverse=True,
        )
        section_counts = {
            "arxiv": len(arxiv_papers),
            **{
                name: sum(
                    paper.get("conference") == name for paper in conference_papers
                )
                for name in SUPPORTED_CONFERENCES
            },
            "awards": sum(bool(paper.get("awards")) for paper in conference_papers),
        }
        return {
            "papers": papers,
            "categories": categories,
            "conferences": list(SUPPORTED_CONFERENCES),
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
        arxiv_papers, conference_papers = self._collections(data)
        return {
            "refreshing": self._refreshing,
            "updated_at": data.get("updated_at", ""),
            "count": len(self._recent(arxiv_papers)) + len(conference_papers),
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
            old_arxiv, old_conferences = self._collections(cached)
            old_arxiv_by_id = {paper["id"]: paper for paper in old_arxiv}

            try:
                arxiv_papers = self._refresh_arxiv(old_arxiv_by_id)
            except Exception as exc:
                arxiv_papers = old_arxiv
                errors.append(f"arXiv: {exc}")

            conference_papers = []
            for conference in SUPPORTED_CONFERENCES:
                try:
                    fetched = self.openalex.conference_papers(conference)
                    selected = self._classify_conference_papers(fetched, conference)
                    if not selected:
                        raise RuntimeError("主题筛选后没有符合条件的论文")
                    conference_papers.extend(selected)
                except Exception as exc:
                    cached_for_conference = [
                        paper
                        for paper in old_conferences
                        if paper.get("conference") == conference
                    ]
                    conference_papers.extend(cached_for_conference)
                    errors.append(f"{conference}: {exc}")

            self._write_cache(
                {
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                    "arxiv_papers": arxiv_papers,
                    "conference_papers": self._deduplicate(conference_papers),
                }
            )
            self._last_error = "；".join(errors)
        except Exception as exc:
            self._last_error = str(exc)
        finally:
            with self._lock:
                self._refreshing = False

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
            if not categories and conference not in ROBOTICS_CONFERENCES:
                continue
            if not categories:
                categories = ["机器人学习"]
                evidence = [conference]
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
    def _collections(data: dict) -> tuple[list[dict], list[dict]]:
        if "arxiv_papers" in data or "conference_papers" in data:
            return data.get("arxiv_papers", []), data.get("conference_papers", [])
        return data.get("papers", []), []

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
            key = paper.get("doi") or normalize_text(paper.get("title", ""))
            if key:
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
