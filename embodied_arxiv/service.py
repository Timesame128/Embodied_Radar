from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

from embodied_arxiv.arxiv_client import ArxivClient
from embodied_arxiv.classifier import classify, normalize_text
from embodied_arxiv.openalex import OpenAlexClient


class PaperService:
    def __init__(
        self,
        cache_path: str,
        days: int = 15,
        max_results: int = 300,
        openalex_email: str = "",
    ):
        self.cache_path = Path(cache_path)
        self.days = days
        self.arxiv = ArxivClient(max_results=max_results)
        self.openalex = OpenAlexClient(email=openalex_email)
        self._lock = threading.Lock()
        self._refreshing = False
        self._last_error = ""

    def list_papers(self, category: str = "", keyword: str = "") -> dict:
        data = self._read_cache()
        papers = self._recent(data.get("papers", []))
        if category:
            papers = [paper for paper in papers if category in paper.get("embodied_categories", [])]
        if keyword:
            needle = normalize_text(keyword)
            papers = [
                paper
                for paper in papers
                if needle
                in normalize_text(
                    " ".join(
                        [
                            paper.get("title", ""),
                            paper.get("summary", ""),
                            " ".join(paper.get("authors", [])),
                            " ".join(paper.get("institutions", [])),
                        ]
                    )
                )
            ]
        categories = sorted(
            {item for paper in self._recent(data.get("papers", [])) for item in paper["embodied_categories"]}
        )
        return {
            "papers": papers,
            "categories": categories,
            "count": len(papers),
            "days": self.days,
            "updated_at": data.get("updated_at", ""),
            "refreshing": self._refreshing,
            "last_error": self._last_error,
        }

    def status(self) -> dict:
        data = self._read_cache()
        return {
            "refreshing": self._refreshing,
            "updated_at": data.get("updated_at", ""),
            "count": len(self._recent(data.get("papers", []))),
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
        try:
            existing = {paper["id"]: paper for paper in self._read_cache().get("papers", [])}
            candidates = self.arxiv.fetch()
            selected = []
            for paper in self._recent(candidates):
                categories, evidence = classify(paper["title"], paper["summary"])
                if not categories:
                    continue
                paper["embodied_categories"] = categories
                paper["match_evidence"] = evidence
                old = existing.get(paper["id"], {})
                paper["institutions"] = old.get("institutions", [])
                paper["institutions_source"] = old.get("institutions_source", "")
                selected.append(paper)

            # Enrich a bounded number per refresh to stay friendly to OpenAlex.
            for paper in [item for item in selected if not item["institutions"]][:30]:
                try:
                    institutions = self.openalex.institutions_for(paper["title"])
                    if institutions:
                        paper["institutions"] = institutions
                        paper["institutions_source"] = "OpenAlex"
                except Exception:
                    continue

            selected.sort(key=lambda item: item["published_ts"], reverse=True)
            self._write_cache(
                {
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                    "papers": selected,
                }
            )
            self._last_error = ""
        except Exception as exc:
            self._last_error = str(exc)
        finally:
            with self._lock:
                self._refreshing = False

    def _recent(self, papers: list[dict]) -> list[dict]:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=self.days)).timestamp()
        return [paper for paper in papers if paper.get("published_ts", 0) >= cutoff]

    def _read_cache(self) -> dict:
        if not self.cache_path.exists():
            return {"updated_at": "", "papers": []}
        try:
            return json.loads(self.cache_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"updated_at": "", "papers": []}

    def _write_cache(self, data: dict) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.cache_path.with_suffix(".tmp")
        temp_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(temp_path, self.cache_path)

