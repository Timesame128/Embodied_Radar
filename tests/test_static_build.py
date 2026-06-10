import json
from pathlib import Path

from build_static import build


def test_static_build_uses_relative_assets(tmp_path: Path):
    output = tmp_path / "site"
    data = build(output)

    html = (output / "index.html").read_text(encoding="utf-8")
    payload = json.loads((output / "data" / "papers.json").read_text(encoding="utf-8"))

    assert './data/papers.json' in html
    assert './style.css' in html
    assert '{{' not in html
    assert payload["count"] == len(payload["papers"])
    assert data["papers"]

