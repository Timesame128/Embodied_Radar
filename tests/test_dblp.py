from datetime import datetime, timezone

import requests

from embodied_arxiv.dblp import DblpClient, _parse_hit


def test_parse_dblp_hit():
    paper = _parse_hit(
        {
            "key": "conf/corl/Example25",
            "title": "Robot Learning Example.",
            "authors": {
                "author": [
                    {"text": "Ada Example"},
                    {"text": "Grace Example"},
                ]
            },
            "venue": "CoRL",
            "year": "2025",
            "doi": "10.1000/example",
            "ee": ["https://doi.org/10.1000/example"],
            "url": "rec/conf/corl/Example25",
        },
        "CoRL",
    )

    assert paper["id"] == "dblp:conf/corl/Example25"
    assert paper["title"] == "Robot Learning Example"
    assert paper["authors"] == ["Ada Example", "Grace Example"]
    assert paper["publication_year"] == 2025
    assert paper["conference"] == "CoRL"


def test_dblp_paginates_and_balances_years(monkeypatch):
    current_year = datetime.now(timezone.utc).year
    pages = [
        [
            {
                "info": {
                    "key": f"conf/icra/current{index}",
                    "title": f"Current Robot Paper {index}",
                    "year": str(current_year),
                }
            }
            for index in range(4)
        ],
        [
            {
                "info": {
                    "key": f"conf/icra/previous{index}",
                    "title": f"Previous Robot Paper {index}",
                    "year": str(current_year - 1),
                }
            }
            for index in range(4)
        ],
    ]
    calls = []

    class Response:
        def __init__(self, hits):
            self.hits = hits

        def raise_for_status(self):
            return None

        def json(self):
            return {"result": {"hits": {"hit": self.hits}}}

    def fake_get(url, params, timeout, headers):
        calls.append(params)
        page = len(calls) - 1
        return Response(pages[page] if page < len(pages) else [])

    monkeypatch.setattr(requests, "get", fake_get)

    papers = DblpClient(max_results=4, years=2).conference_papers("ICRA")

    assert [call["f"] for call in calls] == [0, 1000]
    assert [paper["publication_year"] for paper in papers].count(current_year) == 2
    assert [paper["publication_year"] for paper in papers].count(current_year - 1) == 2
