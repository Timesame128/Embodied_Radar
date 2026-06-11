import time

from embodied_arxiv.conferences import detect_conferences
from embodied_arxiv.service import PaperService


def test_detects_acronyms_and_full_names():
    assert detect_conferences("Accepted to CoRL 2026") == ["CoRL"]
    assert detect_conferences("International Conference on Robotics and Automation 2025") == [
        "ICRA"
    ]
    assert detect_conferences("Robotics: Science and Systems 2024") == ["RSS"]


def test_normalizes_nips_to_neurips():
    assert detect_conferences("NeurIPS 2025") == ["NeurIPS"]
    assert detect_conferences("NIPS 2017") == ["NeurIPS"]


def test_does_not_treat_unrelated_rss_as_conference():
    assert detect_conferences("Subscribe to our RSS feed") == []


def test_detects_multiple_conference_mentions():
    assert detect_conferences("ICLR 2026 workshop; extended version for ICML 2026") == [
        "ICLR",
        "ICML",
    ]


def test_legacy_arxiv_cache_stays_separate_from_conference_sections(tmp_path):
    cache_path = tmp_path / "papers.json"
    service = PaperService(cache_path=str(cache_path), days=15)
    now = time.time()
    service._write_cache(
        {
            "updated_at": "",
            "papers": [
                {
                    "id": "example",
                    "title": "Robot Learning",
                    "summary": "A robot manipulation paper.",
                    "authors": [],
                    "institutions": [],
                    "published_ts": now,
                    "embodied_categories": ["操作与抓取"],
                    "comment": "Accepted to CoRL 2026",
                    "journal_ref": "",
                }
            ],
        }
    )

    arxiv_data = service.list_papers(source="arxiv")
    conference_data = service.list_papers(source="CoRL")

    assert arxiv_data["count"] == 1
    assert arxiv_data["papers"][0]["conferences"] == ["CoRL"]
    assert conference_data["count"] == 0
