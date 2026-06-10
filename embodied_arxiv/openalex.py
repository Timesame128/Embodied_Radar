from __future__ import annotations

import re
from difflib import SequenceMatcher

import requests


class OpenAlexClient:
    endpoint = "https://api.openalex.org/works"

    def __init__(self, email: str = "", timeout: int = 15):
        self.email = email
        self.timeout = timeout

    def institutions_for(self, title: str) -> list[str]:
        params = {"search": title, "per-page": 3}
        if self.email:
            params["mailto"] = self.email
        response = requests.get(
            self.endpoint,
            params=params,
            timeout=self.timeout,
            headers={"User-Agent": "EmbodiedArxivRadar/1.0"},
        )
        response.raise_for_status()
        normalized = _normalize(title)
        for work in response.json().get("results", []):
            candidate = _normalize(work.get("title", ""))
            if SequenceMatcher(None, normalized, candidate).ratio() < 0.9:
                continue
            names = []
            for authorship in work.get("authorships", []):
                for institution in authorship.get("institutions", []):
                    if institution.get("display_name"):
                        names.append(institution["display_name"])
            return list(dict.fromkeys(names))
        return []


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()

