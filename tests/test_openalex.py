from datetime import date

from embodied_arxiv.openalex import OpenAlexClient, _source_matches


WORK = {
    "id": "https://openalex.org/W123",
    "doi": "https://doi.org/10.1000/example",
    "display_name": "A Robot Manipulation Paper",
    "publication_date": "2025-07-15",
    "publication_year": 2025,
    "cited_by_count": 42,
    "abstract_inverted_index": {
        "Robot": [0],
        "manipulation": [1],
        "works": [2],
    },
    "authorships": [
        {
            "author": {"display_name": "Ada Example"},
            "institutions": [{"display_name": "Example Lab"}],
        }
    ],
    "primary_location": {
        "landing_page_url": "https://example.org/paper",
        "pdf_url": "https://example.org/paper.pdf",
        "source": {"display_name": "Conference on Robot Learning"},
    },
    "ids": {"arxiv": "https://arxiv.org/abs/2501.12345"},
}


def test_parse_conference_work():
    paper = OpenAlexClient._parse_work(WORK, "CoRL")

    assert paper["id"] == "openalex:W123"
    assert paper["conference"] == "CoRL"
    assert paper["summary"] == "Robot manipulation works"
    assert paper["authors"] == ["Ada Example"]
    assert paper["institutions"] == ["Example Lab"]
    assert paper["cited_by_count"] == 42
    assert paper["publication_year"] == 2025
    assert paper["arxiv_url"].endswith("2501.12345")


def test_source_name_matching_accepts_numbered_proceedings():
    assert _source_matches(
        "proceedings of the 8th conference on robot learning",
        ["conference on robot learning", "corl"],
    )
    assert _source_matches(
        "2025 ieee cvf conference on computer vision and pattern recognition",
        [
            "ieee cvf conference on computer vision and pattern recognition",
            "cvpr",
        ],
    )


def test_conference_fetches_are_split_by_year(monkeypatch):
    client = OpenAlexClient(conference_max_results=4, conference_years=2)
    current_year = date.today().year
    filters = []

    monkeypatch.setattr(client, "_source_ids", lambda conference, years: ["S1"])

    def fake_get(url, params):
        filters.append(params["filter"])
        year = current_year if f"{current_year}-01-01" in params["filter"] else current_year - 1
        return {
            "results": [
                {
                    **WORK,
                    "id": f"https://openalex.org/W{year}",
                    "doi": f"https://doi.org/10.1000/{year}",
                    "title": f"Robot Manipulation Paper {year}",
                    "display_name": f"Robot Manipulation Paper {year}",
                    "publication_date": f"{year}-07-15",
                    "publication_year": year,
                }
            ],
            "meta": {"next_cursor": None},
        }

    monkeypatch.setattr(client, "_get", fake_get)

    papers = client.conference_papers("CoRL")

    assert [paper["publication_year"] for paper in papers] == [
        current_year,
        current_year - 1,
    ]
    assert any(f"from_publication_date:{current_year}-01-01" in item for item in filters)
    assert any(f"to_publication_date:{current_year - 1}-12-31" in item for item in filters)


def test_source_lookup_uses_year_qualified_queries(monkeypatch):
    client = OpenAlexClient()
    queries = []

    def fake_get(url, params):
        queries.append(params["search"])
        return {
            "results": [
                {
                    "id": "https://openalex.org/S123",
                    "display_name": "2026 IEEE International Conference on Robotics and Automation",
                    "type": "conference",
                }
            ]
        }

    monkeypatch.setattr(client, "_get", fake_get)

    assert client._source_ids("ICRA", [2026]) == ["S123"]
    assert queries[0].endswith("2026")
