from __future__ import annotations

import json
import re
from pathlib import Path


class AwardCatalog:
    def __init__(self, path: str):
        self.path = Path(path)

    def apply(self, papers: list[dict]) -> list[dict]:
        awards = self._read()
        prepared = []
        for paper in papers:
            item = dict(paper)
            item["awards"] = [
                award
                for award in awards
                if _matches(item, award)
            ]
            prepared.append(item)
        return prepared

    def _read(self) -> list[dict]:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        return data.get("awards", [])


def _normalize_title(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _normalize_doi(value: str) -> str:
    return value.lower().removeprefix("https://doi.org/").strip()


def _matches(paper: dict, award: dict) -> bool:
    paper_doi = _normalize_doi(paper.get("doi", ""))
    award_doi = _normalize_doi(award.get("doi", ""))
    identity_matches = (
        bool(paper_doi and award_doi and paper_doi == award_doi)
        or _normalize_title(paper.get("title", ""))
        == _normalize_title(award.get("title", ""))
    )
    if not identity_matches:
        return False
    if award.get("conference") and award["conference"] != paper.get("conference"):
        return False
    if award.get("year") and award["year"] != paper.get("publication_year"):
        return False
    return True
