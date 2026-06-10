from __future__ import annotations

import os
import threading
import time
from datetime import datetime, timezone

from flask import Flask, jsonify, render_template, request

from embodied_arxiv.service import PaperService


def create_app(testing: bool = False) -> Flask:
    app = Flask(__name__)
    app.config["JSON_AS_ASCII"] = False
    app.config["TESTING"] = testing

    service = PaperService(
        cache_path=os.getenv("CACHE_PATH", "data/papers.json"),
        days=int(os.getenv("PAPER_DAYS", "15")),
        max_results=int(os.getenv("ARXIV_MAX_RESULTS", "300")),
        openalex_email=os.getenv("OPENALEX_EMAIL", ""),
    )
    app.extensions["paper_service"] = service

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/papers")
    def papers():
        category = request.args.get("category", "").strip()
        keyword = request.args.get("q", "").strip()
        return jsonify(service.list_papers(category=category, keyword=keyword))

    @app.get("/api/status")
    def status():
        return jsonify(service.status())

    @app.post("/api/refresh")
    def refresh():
        if not service.start_refresh():
            return jsonify({"ok": False, "message": "刷新任务正在运行"}), 409
        return jsonify({"ok": True, "message": "已开始刷新"})

    if not testing and os.getenv("DISABLE_SCHEDULER", "0") != "1":
        start_scheduler(service)

    return app


def start_scheduler(service: PaperService) -> None:
    interval = max(30, int(os.getenv("REFRESH_INTERVAL_MINUTES", "360"))) * 60

    def run() -> None:
        time.sleep(1)
        while True:
            service.refresh()
            time.sleep(interval)

    threading.Thread(target=run, name="paper-refresh-scheduler", daemon=True).start()


app = create_app()

if __name__ == "__main__":
    app.run(
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "5000")),
        debug=os.getenv("FLASK_DEBUG", "0") == "1",
        use_reloader=False,
    )

