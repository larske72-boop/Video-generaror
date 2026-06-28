"""Hoofd pipeline voor football shorts — directe ffmpeg verwerking, geen MoviePy."""

import time
from pathlib import Path
from typing import Optional

import yaml

from .downloader import download_clips, load_urls_from_file
from .processor import (
    TARGET_W, TARGET_H,
    make_intro_video,
    process_clip,
    concat_and_export,
    extract_frame,
)
from .overlays import make_thumbnail

DEFAULT_CONFIG = Path(__file__).parent.parent / "config.yaml"


def _log(msg: str) -> None:
    print(msg, flush=True)


def load_config(config_path: Optional[Path] = None) -> dict:
    with open(config_path or DEFAULT_CONFIG) as f:
        return yaml.safe_load(f)


class FootballShortsGenerator:
    def __init__(
        self,
        config_path: Optional[Path] = None,
        output_dir: Optional[Path] = None,
    ):
        self.config = load_config(config_path)
        self.output_dir = output_dir or Path(self.config["output"]["output_dir"])
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_short(
        self,
        sources: list[str],
        template: str = "skill_move",
        player_name: str = "",
        club: str = "",
        title: str = "",
        music_path: Optional[Path] = None,
        add_thumbnail: bool = True,
        team_a: str = "",
        score_a: int = 0,
        score_b: int = 0,
        team_b: str = "",
    ) -> Path:
        tmpl_cfg = self.config["templates"].get(template)
        if not tmpl_cfg:
            raise ValueError(f"Onbekend template '{template}'.")

        used_title = title or tmpl_cfg.get("title", "FOOTBALL!")
        channel    = self.config["branding"]["channel_name"]
        accent     = self.config["text"]["accent_color"]
        primary    = self.config["text"]["primary_color"]
        timestamp  = int(time.time())

        job_dir = self.output_dir / f"{template}_{timestamp}"
        job_dir.mkdir(parents=True, exist_ok=True)

        _log(f"Template : {template} — {tmpl_cfg['label']}")
        _log(f"Bronnen  : {len(sources)} clip(s)" + (f"  |  Speler: {player_name}" if player_name else ""))

        # ── Stap 1: clips downloaden ──────────────────────────────────
        _log("Stap 1: Clips downloaden...")
        video_paths = self._collect_clips(sources, job_dir)
        if not video_paths:
            raise RuntimeError(
                "Download mislukt. Controleer of de YouTube-link klopt "
                "en of de video publiek beschikbaar is."
            )
        _log(f"  ✓ {len(video_paths)} clip(s) gedownload")

        # ── Stap 2: clips verwerken ───────────────────────────────────
        _log("Stap 2: Clips verwerken (9:16 formaat + overlays)...")
        processed: list[Path] = []
        for i, raw in enumerate(video_paths):
            out = job_dir / f"clip_{i:02d}.mp4"
            is_last = (i == len(video_paths) - 1)
            _log(f"  [{i+1}/{len(video_paths)}] {raw.name}")
            try:
                process_clip(
                    input_path=raw,
                    output_path=out,
                    trim_sec=float(tmpl_cfg.get("clip_trim", 8)),
                    slow_motion=tmpl_cfg.get("slow_motion", False),
                    player_name=player_name,
                    club=club,
                    channel_name=channel,
                    show_title=is_last,
                    title=used_title,
                    subtitle=f"{player_name} | {club}" if player_name and club else player_name,
                    accent=accent,
                    primary=primary,
                )
                processed.append(out)
                _log(f"  ✓ Clip {i+1} klaar")
            except Exception as exc:
                import traceback
                _log(f"  ✗ Clip {i+1} mislukt: {exc}")
                _log(traceback.format_exc())

        if not processed:
            raise RuntimeError("Geen clips konden worden verwerkt.")

        # ── Stap 3: intro maken ───────────────────────────────────────
        _log("Stap 3: Samenvoegen...")
        intro_path = job_dir / "intro.mp4"
        try:
            make_intro_video(channel, intro_path, duration=1.5)
        except Exception as exc:
            _log(f"  ⚠ Intro overgeslagen: {exc}")
            intro_path = None

        # ── Stap 4: concat + export ───────────────────────────────────
        slug = (player_name or "short").replace(" ", "_")
        output_path = self.output_dir / f"{template}_{slug}_{timestamp}.mp4"

        concat_and_export(
            clip_paths=processed,
            output_path=output_path,
            intro_path=intro_path if (intro_path and intro_path.exists()) else None,
            max_duration=self.config["output"]["max_duration"],
            music_path=music_path,
            music_volume=tmpl_cfg.get("music_volume", 0.20),
        )

        # ── Stap 5: thumbnail ─────────────────────────────────────────
        if add_thumbnail:
            _log("Stap 4: Thumbnail maken...")
            thumb_path = output_path.with_suffix(".jpg")
            try:
                frame = extract_frame(output_path, t=2.0)
                make_thumbnail(frame, title=used_title, output_path=thumb_path, accent=accent)
                _log(f"  ✓ Thumbnail opgeslagen")
            except Exception as exc:
                _log(f"  ⚠ Thumbnail mislukt: {exc}")

        _log(f"✓ Short klaar! {output_path.name}")
        return output_path

    def _collect_clips(self, sources: list[str], job_dir: Path) -> list[Path]:
        local: list[Path] = []
        urls:  list[str]  = []
        for src in sources:
            p = Path(src)
            if p.exists() and p.suffix.lower() in {".mp4", ".mov", ".webm", ".mkv", ".avi"}:
                local.append(p)
            else:
                urls.append(src)
        downloaded: list[Path] = []
        if urls:
            downloaded = download_clips(urls=urls, dest_dir=job_dir / "downloads")
        return local + downloaded

    def batch_from_file(
        self,
        urls_file: Path,
        clips_per_short: int = 3,
        template: str = "skill_move",
        music_path: Optional[Path] = None,
        **kwargs,
    ) -> list[Path]:
        all_urls = load_urls_from_file(urls_file)
        results = []
        for i in range(0, len(all_urls), clips_per_short):
            batch = all_urls[i:i + clips_per_short]
            _log(f"\n=== Short {i // clips_per_short + 1} ===")
            try:
                results.append(self.generate_short(
                    sources=batch, template=template, music_path=music_path, **kwargs
                ))
            except Exception as exc:
                _log(f"Short mislukt: {exc}")
        return results
