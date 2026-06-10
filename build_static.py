from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from embodied_arxiv.service import PaperService


ROOT = Path(__file__).resolve().parent


def build(output_dir: Path, refresh: bool = False) -> dict:
    service = PaperService(
        cache_path=str(ROOT / "data" / "papers.json"),
        days=15,
        max_results=300,
    )
    if refresh:
        service.refresh()

    data = service.list_papers()
    if not data["papers"]:
        error = data.get("last_error") or "缓存中没有最近 15 天的论文"
        raise RuntimeError(f"无法构建站点：{error}")

    if output_dir.exists():
        shutil.rmtree(output_dir)
    (output_dir / "data").mkdir(parents=True)

    environment = Environment(
        loader=FileSystemLoader(ROOT / "templates"),
        autoescape=select_autoescape(["html"]),
    )
    html = environment.get_template("index.html").render(
        papers_url="./data/papers.json",
        refresh_url="",
        deployment_mode="static",
        style_url="./style.css",
        script_url="./app.js",
    )
    (output_dir / "index.html").write_text(html, encoding="utf-8")
    shutil.copy2(ROOT / "static" / "style.css", output_dir / "style.css")
    shutil.copy2(ROOT / "static" / "app.js", output_dir / "app.js")
    (output_dir / ".nojekyll").write_text("", encoding="utf-8")

    public_data = {
        **data,
        "refreshing": False,
        "last_error": "",
    }
    (output_dir / "data" / "papers.json").write_text(
        json.dumps(public_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return public_data


def main() -> None:
    parser = argparse.ArgumentParser(description="构建 GitHub Pages 静态站点")
    parser.add_argument("--output", default="_site")
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    data = build(ROOT / args.output, refresh=args.refresh)
    print(f"Built {len(data['papers'])} papers into {args.output}")


if __name__ == "__main__":
    main()

