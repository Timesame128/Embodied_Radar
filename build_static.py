from __future__ import annotations

import argparse
import json
import os
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
        openalex_email=os.getenv("OPENALEX_EMAIL", ""),
        openalex_api_key=os.getenv("OPENALEX_API_KEY", ""),
        conference_max_results=int(os.getenv("CONFERENCE_MAX_RESULTS", "200")),
        conference_years=int(os.getenv("CONFERENCE_YEARS", "5")),
        conference_refresh_hours=int(
            os.getenv("CONFERENCE_REFRESH_HOURS", "168")
        ),
        journal_max_results=int(os.getenv("JOURNAL_MAX_RESULTS", "200")),
        journal_years=int(os.getenv("JOURNAL_YEARS", "5")),
        journal_refresh_hours=int(
            os.getenv("JOURNAL_REFRESH_HOURS", "168")
        ),
        awards_path=str(ROOT / "data" / "awards.json"),
    )
    if refresh:
        service.refresh()

    data = service.list_papers()
    if not data["papers"]:
        error = data.get("last_error") or "缓存中没有最近 15 天的论文"
        raise RuntimeError(f"无法构建站点：{error}")
    if os.getenv("REQUIRE_CONFERENCE_DATA", "0") == "1":
        missing = [
            conference
            for conference in data["conferences"]
            if data["section_counts"].get(conference, 0) == 0
        ]
        if missing:
            details = data.get("last_error") or "未返回错误详情"
            raise RuntimeError(
                f"会议数据同步不完整：{', '.join(missing)}。{details}"
            )

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
        icon_url="./site-icon.png",
        asset_version="scrollbar-thumb-20260810",
    )
    (output_dir / "index.html").write_text(html, encoding="utf-8")
    shutil.copy2(ROOT / "static" / "style.css", output_dir / "style.css")
    shutil.copy2(ROOT / "static" / "app.js", output_dir / "app.js")
    shutil.copy2(ROOT / "static" / "site-icon.png", output_dir / "site-icon.png")
    (output_dir / ".nojekyll").write_text("", encoding="utf-8")

    public_data = {
        **data,
        "refreshing": False,
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
