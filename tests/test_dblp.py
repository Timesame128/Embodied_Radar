from embodied_arxiv.dblp import _parse_hit


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
