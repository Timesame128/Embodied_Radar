import json
import time
from datetime import datetime, timedelta, timezone

import embodied_arxiv.service as service_module
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
    conference_data = service.list_papers(source="conference")

    assert [paper["id"] for paper in data["papers"]] == ["two"]
    assert data["section_counts"]["CoRL"] == 2
    assert data["section_counts"]["ICRA"] == 1
    assert data["section_counts"]["conference"] == 3
    assert conference_data["count"] == 3


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


def test_fresh_conference_cache_skips_network_fetch(tmp_path, monkeypatch):
    monkeypatch.setattr(service_module, "SUPPORTED_CONFERENCES", ("ICRA",))
    monkeypatch.setattr(service_module, "SUPPORTED_JOURNALS", ())
    now = datetime.now(timezone.utc)
    cache_path = tmp_path / "papers.json"
    service = PaperService(
        cache_path=str(cache_path),
        conference_refresh_hours=168,
    )
    service._write_cache(
        {
            "updated_at": now.isoformat(),
            "conference_updated_at": {"ICRA": now.isoformat()},
            "arxiv_papers": [],
            "conference_papers": [
                _paper("old", "ICRA", 2025, 10, "Cached Robot Paper"),
            ],
        }
    )
    service._refresh_arxiv = lambda existing: []

    def fail_fetch(conference):
        raise AssertionError(f"unexpected conference fetch: {conference}")

    service._fetch_conference = fail_fetch
    service.refresh()

    cached = service._read_cache()
    assert [paper["id"] for paper in cached["conference_papers"]] == ["old"]
    assert service._last_error == ""


def test_stale_conference_refresh_appends_without_deleting(tmp_path, monkeypatch):
    monkeypatch.setattr(service_module, "SUPPORTED_CONFERENCES", ("ICRA",))
    monkeypatch.setattr(service_module, "SUPPORTED_JOURNALS", ())
    old_refresh = datetime.now(timezone.utc) - timedelta(days=8)
    cache_path = tmp_path / "papers.json"
    service = PaperService(
        cache_path=str(cache_path),
        conference_refresh_hours=168,
    )
    service._write_cache(
        {
            "updated_at": old_refresh.isoformat(),
            "conference_updated_at": {"ICRA": old_refresh.isoformat()},
            "arxiv_papers": [],
            "conference_papers": [
                _paper("old", "ICRA", 2024, 10, "Older Robot Paper"),
            ],
        }
    )
    service._refresh_arxiv = lambda existing: []
    service._fetch_conference = lambda conference: [
        _paper("new", conference, 2025, 0, "New Robot Paper"),
    ]
    service.refresh()

    cached = service._read_cache()
    assert {paper["id"] for paper in cached["conference_papers"]} == {
        "old",
        "new",
    }
    assert cached["conference_updated_at"]["ICRA"] != old_refresh.isoformat()


def test_failed_stale_refresh_keeps_cached_conference(tmp_path, monkeypatch):
    monkeypatch.setattr(service_module, "SUPPORTED_CONFERENCES", ("ICRA",))
    monkeypatch.setattr(service_module, "SUPPORTED_JOURNALS", ())
    old_refresh = datetime.now(timezone.utc) - timedelta(days=8)
    cache_path = tmp_path / "papers.json"
    service = PaperService(cache_path=str(cache_path))
    service._write_cache(
        {
            "updated_at": old_refresh.isoformat(),
            "conference_updated_at": {"ICRA": old_refresh.isoformat()},
            "arxiv_papers": [],
            "conference_papers": [
                _paper("old", "ICRA", 2024, 10, "Older Robot Paper"),
            ],
        }
    )
    service._refresh_arxiv = lambda existing: []
    attempts = []

    def fail_fetch(conference):
        attempts.append(conference)
        raise RuntimeError("temporary upstream failure")

    service._fetch_conference = fail_fetch
    service.refresh()
    first_error = service._last_error
    service.refresh()

    cached = service._read_cache()
    assert [paper["id"] for paper in cached["conference_papers"]] == ["old"]
    assert cached["conference_updated_at"]["ICRA"] == old_refresh.isoformat()
    assert cached["conference_checked_at"]["ICRA"] != old_refresh.isoformat()
    assert attempts == ["ICRA"]
    assert first_error == "ICRA: temporary upstream failure"
    assert service._last_error == ""


def test_journal_source_filter_and_counts(tmp_path):
    service = PaperService(cache_path=str(tmp_path / "papers.json"))
    paper = {
        **_paper("journal-one", "", 2025, 12, "Journal Robot Paper"),
        "source_kind": "journal",
        "journal": "T-RO",
        "conference": "",
        "venue": "IEEE Transactions on Robotics",
    }
    service._write_cache(
        {
            "updated_at": "",
            "arxiv_papers": [],
            "conference_papers": [],
            "journal_papers": [paper],
        }
    )

    data = service.list_papers(source="T-RO")
    journal_data = service.list_papers(source="journal")

    assert [item["id"] for item in data["papers"]] == ["journal-one"]
    assert data["section_counts"]["T-RO"] == 1
    assert data["section_counts"]["journal"] == 1
    assert journal_data["count"] == 1
    assert data["journals"] == ["Science Robotics", "IJRR", "T-RO"]


def test_stale_journal_refresh_appends_without_deleting(tmp_path, monkeypatch):
    monkeypatch.setattr(service_module, "SUPPORTED_CONFERENCES", ())
    monkeypatch.setattr(service_module, "SUPPORTED_JOURNALS", ("T-RO",))
    old_refresh = datetime.now(timezone.utc) - timedelta(days=8)
    service = PaperService(cache_path=str(tmp_path / "papers.json"))
    old_paper = {
        **_paper("old-journal", "", 2024, 10, "Older Journal Robot Paper"),
        "source_kind": "journal",
        "journal": "T-RO",
        "conference": "",
    }
    new_paper = {
        **_paper("new-journal", "", 2025, 0, "New Journal Robot Paper"),
        "source_kind": "journal",
        "journal": "T-RO",
        "conference": "",
    }
    service._write_cache(
        {
            "updated_at": old_refresh.isoformat(),
            "journal_updated_at": {"T-RO": old_refresh.isoformat()},
            "journal_checked_at": {"T-RO": old_refresh.isoformat()},
            "arxiv_papers": [],
            "conference_papers": [],
            "journal_papers": [old_paper],
        }
    )
    service._refresh_arxiv = lambda existing: []
    service.openalex.journal_papers = lambda journal: [new_paper]
    service.refresh()

    cached = service._read_cache()
    assert {paper["id"] for paper in cached["journal_papers"]} == {
        "old-journal",
        "new-journal",
    }
    assert cached["journal_updated_at"]["T-RO"] != old_refresh.isoformat()
