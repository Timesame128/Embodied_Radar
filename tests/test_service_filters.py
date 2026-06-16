import json
import time

from embodied_arxiv.service import PaperService


def _paper(identifier, conference, year, citations, title, awards=None):
    return {
        "id": identifier,
        "source_kind": "conference",
        "conference": conference,
        "title": title,
        "summary": "A robot manipulation policy.",
        "authors": [],
        "institutions": [],
        "published": f"{year}-01-01",
        "published_ts": time.mktime((year, 1, 1, 0, 0, 0, 0, 0, -1)),
        "publication_year": year,
        "cited_by_count": citations,
        "embodied_categories": ["操作与抓取"],
        "awards": awards or [],
    }


def test_conference_sort_and_range_filters(tmp_path):
    cache_path = tmp_path / "papers.json"
    service = PaperService(cache_path=str(cache_path))
    service._write_cache(
        {
            "updated_at": "",
            "arxiv_papers": [],
            "conference_papers": [
                _paper("one", "CoRL", 2024, 10, "Paper One"),
                _paper("two", "CoRL", 2025, 80, "Paper Two"),
                _paper("three", "ICRA", 2025, 100, "Paper Three"),
            ],
        }
    )

    data = service.list_papers(
        source="CoRL",
        sort="citations_desc",
        from_year=2024,
        to_year=2025,
        min_citations=20,
    )

    assert [paper["id"] for paper in data["papers"]] == ["two"]
    assert data["section_counts"]["CoRL"] == 2
    assert data["section_counts"]["ICRA"] == 1


def test_award_section_uses_curated_catalog(tmp_path):
    cache_path = tmp_path / "papers.json"
    awards_path = tmp_path / "awards.json"
    awards_path.write_text(
        json.dumps(
            {
                "awards": [
                    {
                        "title": "Paper Two",
                        "conference": "CoRL",
                        "year": 2025,
                        "award": "Best Paper",
                        "source_url": "https://example.org/awards",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    service = PaperService(
        cache_path=str(cache_path),
        awards_path=str(awards_path),
    )
    service._write_cache(
        {
            "updated_at": "",
            "arxiv_papers": [],
            "conference_papers": [
                _paper("one", "CoRL", 2024, 10, "Paper One"),
                _paper("two", "CoRL", 2025, 80, "Paper Two"),
            ],
        }
    )

    data = service.list_papers(source="awards")

    assert data["count"] == 1
    assert data["papers"][0]["awards"][0]["award"] == "Best Paper"


def test_award_does_not_cross_conference_boundary(tmp_path):
    cache_path = tmp_path / "papers.json"
    awards_path = tmp_path / "awards.json"
    awards_path.write_text(
        json.dumps(
            {
                "awards": [
                    {
                        "title": "Shared Title",
                        "conference": "ICRA",
                        "year": 2025,
                        "award": "Best Paper",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    service = PaperService(
        cache_path=str(cache_path),
        awards_path=str(awards_path),
    )
    service._write_cache(
        {
            "updated_at": "",
            "arxiv_papers": [],
            "conference_papers": [
                _paper("one", "CoRL", 2025, 10, "Shared Title"),
            ],
        }
    )

    assert service.list_papers(source="awards")["count"] == 0


def test_fetch_conference_merges_openalex_and_dblp(tmp_path):
    service = PaperService(cache_path=str(tmp_path / "papers.json"))
    openalex_paper = {
        **_paper(
            "openalex:one",
            "ICRA",
            2025,
            42,
            "Shared Robot Paper",
        ),
        "doi": "10.1000/shared",
        "openalex_id": "W1",
        "summary": "Robot manipulation with institutions.",
        "institutions": ["Example Lab"],
    }
    dblp_duplicate = {
        **_paper("dblp:one", "ICRA", 2025, 0, "Shared Robot Paper"),
        "doi": "10.1000/shared",
    }
    dblp_new = _paper("dblp:two", "ICRA", 2024, 0, "Another Robot Paper")

    service.openalex.conference_papers = lambda conference: [openalex_paper]
    service.dblp.conference_papers = lambda conference: [dblp_duplicate, dblp_new]

    papers = service._fetch_conference("ICRA")

    assert [paper["id"] for paper in papers] == ["openalex:one", "dblp:two"]
    assert papers[0]["institutions"] == ["Example Lab"]


def test_non_robotics_conference_keeps_core_robot_paper():
    paper = {
        **_paper(
            "iclr-robot",
            "ICLR",
            2025,
            0,
            "Robot Learning with Diffusion Policies",
        ),
        "summary": "A benchmark for robot policy learning.",
    }

    selected = PaperService._classify_conference_papers([paper], "ICLR")

    assert len(selected) == 1
    assert selected[0]["embodied_categories"] == ["机器人学习"]
    assert "robot" in selected[0]["match_evidence"]
