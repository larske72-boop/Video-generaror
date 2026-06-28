"""Football Shorts Generator — web-app interface."""

import json
import os
import threading
import time
import uuid
import webbrowser
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_file

app = Flask(__name__)
JOBS: dict[str, dict] = {}
OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)


# ── routes ─────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/generate", methods=["POST"])
def generate():
    data = request.json
    job_id = str(uuid.uuid4())[:8]
    JOBS[job_id] = {"status": "bezig", "log": [], "file": None, "error": None}

    thread = threading.Thread(target=_run_job, args=(job_id, data), daemon=True)
    thread.start()

    return jsonify({"job_id": job_id})


@app.route("/status/<job_id>")
def status(job_id):
    job = JOBS.get(job_id)
    if not job:
        return jsonify({"error": "Job niet gevonden"}), 404
    return jsonify(job)


@app.route("/download/<job_id>")
def download(job_id):
    job = JOBS.get(job_id)
    if not job or not job["file"]:
        return "Bestand niet gevonden", 404
    path = Path(job["file"])
    if not path.exists():
        return "Bestand verwijderd", 404
    return send_file(path, as_attachment=True, download_name=path.name)


# ── achtergrond generatie ───────────────────────────────────────────────────

def _log(job_id, msg):
    JOBS[job_id]["log"].append(msg)


def _run_job(job_id, data):
    try:
        from src.generator import FootballShortsGenerator

        template  = data.get("template", "skill_move")
        player    = data.get("player", "")
        club      = data.get("club", "")
        title     = data.get("title", "")
        urls      = [u.strip() for u in data.get("urls", "").splitlines() if u.strip()]
        music     = data.get("music_path", "")

        if not urls:
            raise ValueError("Voer minimaal één YouTube-link in.")

        _log(job_id, f"▶ Start: {len(urls)} link(s), template: {template}")

        original_log = print

        class LogCapture:
            def write(self, msg):
                msg = msg.strip()
                if msg:
                    _log(job_id, msg)
            def flush(self): pass

        import sys
        sys.stdout = LogCapture()

        try:
            gen = FootballShortsGenerator(output_dir=OUTPUT_DIR)
            path = gen.generate_short(
                sources=urls,
                template=template,
                player_name=player,
                club=club,
                title=title,
                music_path=Path(music) if music and Path(music).exists() else None,
            )
        finally:
            sys.stdout = sys.__stdout__

        JOBS[job_id]["status"] = "klaar"
        JOBS[job_id]["file"] = str(path)
        _log(job_id, f"✓ Video klaar: {path.name}")

    except Exception as exc:
        JOBS[job_id]["status"] = "fout"
        JOBS[job_id]["error"] = str(exc)
        _log(job_id, f"✗ Fout: {exc}")


# ── start ───────────────────────────────────────────────────────────────────

def open_browser():
    time.sleep(1.2)
    webbrowser.open("http://localhost:5000")


if __name__ == "__main__":
    print("=" * 55)
    print("  ⚽ Football Shorts Generator")
    print("  Open in browser: http://localhost:5000")
    print("  iPhone (zelfde WiFi): zie je IP-adres hierboven")
    print("=" * 55)
    threading.Thread(target=open_browser, daemon=True).start()
    app.run(host="0.0.0.0", port=5000, debug=False)
