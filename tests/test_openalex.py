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
