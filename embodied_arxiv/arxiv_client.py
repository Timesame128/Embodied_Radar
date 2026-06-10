from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import datetime
from urllib.parse import urlencode

import requests


ATOM = {"a": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
QUERY_TERMS = [
    '"embodied intelligence"',
    '"embodied ai"',
    '"embodied agent"',
    '"vision language action"',
    '"robot manipulation"',
    '"embodied navigation"',
    '"robot foundation model"',
    '"humanoid robot"',
    '"dexterous manipulation"',
    '"robot locomotion"',
    '"human robot interaction"',
    '"world model" AND robot',
]
URL_RE = re.compile(r"https?://[^\s<>\])}\"']+")


class ArxivClient:
    endpoint = "https://export.arxiv.org/api/query"

    def __init__(self, max_results: int = 300, timeout: int = 30):
        self.max_results = max_results
        self.timeout = timeout

    def fetch(self) -> list[dict]:
        search_query = " OR ".join(f"all:{term}" for term in QUERY_TERMS)
        params = {
            "search_query": search_query,
            "start": 0,
            "max_results": self.max_results,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }
        response = requests.get(
            f"{self.endpoint}?{urlencode(params)}",
            timeout=self.timeout,
            headers={"User-Agent": "EmbodiedArxivRadar/1.0"},
        )
        response.raise_for_status()
        return self.parse(response.text)

    @staticmethod
    def parse(xml_text: str) -> list[dict]:
        root = ET.fromstring(xml_text)
        papers = []
        for entry in root.findall("a:entry", ATOM):
            arxiv_url = _text(entry, "a:id")
            arxiv_id = arxiv_url.rstrip("/").split("/")[-1]
            summary = _clean(_text(entry, "a:summary"))
            comment = _text(entry, "arxiv:comment")
            links = {
                link.attrib.get("title") or link.attrib.get("rel", ""): link.attrib.get("href", "")
                for link in entry.findall("a:link", ATOM)
            }
            external_urls = [
                url.rstrip(".,;")
                for url in URL_RE.findall(f"{summary} {comment}")
                if "arxiv.org" not in url
            ]
            primary = entry.find("arxiv:primary_category", ATOM)
            doi = _text(entry, "arxiv:doi")
            papers.append(
                {
                    "id": arxiv_id,
                    "title": _clean(_text(entry, "a:title")),
                    "summary": summary,
                    "authors": [
                        _clean(_text(author, "a:name"))
                        for author in entry.findall("a:author", ATOM)
                    ],
                    "published": _text(entry, "a:published"),
                    "updated": _text(entry, "a:updated"),
                    "published_ts": _timestamp(_text(entry, "a:published")),
                    "arxiv_url": arxiv_url,
                    "pdf_url": links.get("pdf", f"https://arxiv.org/pdf/{arxiv_id}"),
                    "primary_category": primary.attrib.get("term", "") if primary is not None else "",
                    "arxiv_categories": [
                        node.attrib.get("term", "") for node in entry.findall("a:category", ATOM)
                    ],
                    "comment": comment,
                    "journal_ref": _text(entry, "arxiv:journal_ref"),
                    "doi": doi,
                    "doi_url": f"https://doi.org/{doi}" if doi else "",
                    "external_urls": list(dict.fromkeys(external_urls))[:5],
                }
            )
        return papers


def _text(node: ET.Element, path: str) -> str:
    child = node.find(path, ATOM)
    return child.text.strip() if child is not None and child.text else ""


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _timestamp(value: str) -> float:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()

