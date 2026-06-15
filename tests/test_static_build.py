import json
from pathlib import Path

from build_static import build


def test_static_build_uses_relative_assets(tmp_path: Path):
    output = tmp_path / "site"
    data = build(output)

    html = (output / "index.html").read_text(encoding="utf-8")
    payload = json.loads((output / "data" / "papers.json").read_text(encoding="utf-8"))

    assert './data/papers.json' in html
    assert './style.css?v=aligned-results-20260616' in html
    assert './app.js?v=aligned-results-20260616' in html
    assert './site-icon.png' in html
    assert 'id="categoryFacet"' in html
    assert 'id="timeFacet"' in html
    assert 'id="citationFacet"' in html
    assert 'id="activeFilterTags"' in html
    assert 'id="filterToggleButton"' in html
    assert 'data-view="list"' in html
    assert 'data-view="card"' in html
    assert 'id="immersiveOverlay"' in html
    assert 'id="exitImmersiveButton"' in html
    assert 'id="fromYearInput"' not in html
    assert (output / "site-icon.png").exists()
    assert '{{' not in html
    assert payload["count"] == len(payload["papers"])
    assert data["papers"]
