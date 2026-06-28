"""Hoofd orkestratie pipeline voor football shorts zonder externe AI API."""

import time
from pathlib import Path
from typing import Optional

import yaml
from rich.console import Console
from rich.panel import Panel

from .downloader import download_clips, load_urls_from_file
from .video_editor import (
    build_clip,
    combine_and_export,
    extract_thumbnail_frame,
)
from .overlays import make_thumbnail

console = Console()
DEFAULT_CONFIG = Path(__file__).parent.parent / "config.yaml"


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

    # ------------------------------------------------------------------
    # Hoofd pipeline
    # ------------------------------------------------------------------

    def generate_short(
        self,
        sources: list[str],                 # lokale paden OF YouTube-URLs
        template: str = "goal_celebration",
        player_name: str = "",
        club: str = "",
        title: str = "",
        music_path: Optional[Path] = None,
        add_thumbnail: bool = True,
        # Wedstrijd score (alleen bij match_highlights)
        team_a: str = "",
        score_a: int = 0,
        score_b: int = 0,
        team_b: str = "",
    ) -> Path:
        """Genereer één football short van de opgegeven bronnen."""

        tmpl_cfg = self.config["templates"].get(template)
        if not tmpl_cfg:
            raise ValueError(
                f"Onbekend template '{template}'. "
                f"Kies uit: {list(self.config['templates'].keys())}"
            )

        used_title = title or tmpl_cfg.get("title", "FOOTBALL! ⚽")
        channel = self.config["branding"]["channel_name"]
        timestamp = int(time.time())
        job_dir = self.output_dir / f"{template}_{timestamp}"
        job_dir.mkdir(parents=True, exist_ok=True)

        console.print(Panel(
            f"[bold yellow]Football Shorts Generator[/bold yellow]\n"
            f"Template : [cyan]{template}[/cyan] — {tmpl_cfg['label']}\n"
            f"Bronnen  : [cyan]{len(sources)}[/cyan] clip(s)\n"
            f"Speler   : [cyan]{player_name or '—'}[/cyan]"
            + (f"  |  Club : [cyan]{club}[/cyan]" if club else ""),
            border_style="yellow",
        ))

        # ── Stap 1: clips verzamelen ──────────────────────────────────
        console.print("\n[bold]Stap 1:[/bold] Clips verzamelen...")
        video_paths = self._collect_clips(sources, job_dir)
        if not video_paths:
            raise RuntimeError("Geen bruikbare clips gevonden.")
        console.print(f"  [green]✓[/green] {len(video_paths)} clip(s) beschikbaar")

        # ── Stap 2: clips bewerken ────────────────────────────────────
        console.print("\n[bold]Stap 2:[/bold] Effecten en overlays toepassen...")
        edited = []
        for i, path in enumerate(video_paths):
            console.print(f"  Bewerken [{i + 1}/{len(video_paths)}]: {path.name}")
            is_last = i == len(video_paths) - 1
            try:
                clip = build_clip(
                    video_path=path,
                    template_cfg=tmpl_cfg,
                    global_cfg=self.config,
                    player_name=player_name,
                    club=club,
                    channel_name=channel,
                    show_title=is_last,
                    title=used_title,
                    subtitle=f"{player_name} | {club}" if player_name and club else player_name,
                    show_score=(template == "match_highlights"),
                    team_a=team_a,
                    score_a=score_a,
                    score_b=score_b,
                    team_b=team_b,
                )
                edited.append(clip)
            except Exception as exc:
                console.print(f"  [red]✗[/red] Clip {i + 1} mislukt: {exc}")

        if not edited:
            raise RuntimeError("Geen clips konden worden bewerkt.")

        # ── Stap 3: samenvoegen en exporteren ─────────────────────────
        console.print("\n[bold]Stap 3:[/bold] Clips samenvoegen en exporteren...")
        slug = (player_name or "short").replace(" ", "_")
        out_name = f"{template}_{slug}_{timestamp}.mp4"
        output_path = self.output_dir / out_name

        combine_and_export(
            clips=edited,
            output_path=output_path,
            audio_path=music_path,
            music_volume=tmpl_cfg.get("music_volume", 0.20),
            max_duration=self.config["output"]["max_duration"],
            fps=self.config["output"]["fps"],
            crf=self.config["output"]["crf"],
            fade_duration=self.config["effects"]["fade_duration"],
            include_intro=True,
            channel_name=channel,
        )

        for c in edited:
            try:
                c.close()
            except Exception:
                pass

        # ── Stap 4: thumbnail ─────────────────────────────────────────
        if add_thumbnail:
            console.print("\n[bold]Stap 4:[/bold] Thumbnail maken...")
            thumb_path = output_path.with_suffix(".jpg")
            try:
                frame = extract_thumbnail_frame(output_path, t=2.0)
                make_thumbnail(
                    frame,
                    title=used_title,
                    output_path=thumb_path,
                    accent=self.config["text"]["accent_color"],
                )
                console.print(f"  [green]✓[/green] Thumbnail: {thumb_path.name}")
            except Exception as exc:
                console.print(f"  [yellow]⚠[/yellow] Thumbnail mislukt: {exc}")

        console.print(Panel(
            f"[bold green]✓ Short klaar![/bold green]\n"
            f"Bestand : [cyan]{output_path}[/cyan]\n"
            f"Formaat : [cyan]1080×1920 (9:16)[/cyan]  |  "
            f"Max duur : [cyan]{self.config['output']['max_duration']}s[/cyan]",
            border_style="green",
        ))
        return output_path

    # ------------------------------------------------------------------
    # Batch
    # ------------------------------------------------------------------

    def batch_from_file(
        self,
        urls_file: Path,
        clips_per_short: int = 3,
        template: str = "goal_celebration",
        music_path: Optional[Path] = None,
        **kwargs,
    ) -> list[Path]:
        """Verdeel een URL-bestand in batches en maak per batch een short."""
        all_urls = load_urls_from_file(urls_file)
        results = []
        for i in range(0, len(all_urls), clips_per_short):
            batch = all_urls[i:i + clips_per_short]
            console.print(f"\n[bold magenta]═══ Short {i // clips_per_short + 1} ═══[/bold magenta]")
            try:
                path = self.generate_short(
                    sources=batch,
                    template=template,
                    music_path=music_path,
                    **kwargs,
                )
                results.append(path)
            except Exception as exc:
                console.print(f"[red]Short mislukt:[/red] {exc}")
        return results

    # ------------------------------------------------------------------
    # Intern: clips verzamelen
    # ------------------------------------------------------------------

    def _collect_clips(self, sources: list[str], job_dir: Path) -> list[Path]:
        """Splits bronnen in lokale bestanden en URLs, download URLs."""
        local_paths: list[Path] = []
        urls: list[str] = []

        for src in sources:
            p = Path(src)
            if p.exists() and p.suffix.lower() in {".mp4", ".mov", ".webm", ".mkv", ".avi"}:
                local_paths.append(p)
            else:
                urls.append(src)

        downloaded: list[Path] = []
        if urls:
            dl_cfg = self.config["download"]
            downloaded = download_clips(
                urls=urls,
                dest_dir=job_dir / "downloads",
                quality=dl_cfg["quality"],
                merge_format=dl_cfg["merge_format"],
                max_duration=dl_cfg["max_clip_duration"],
            )

        return local_paths + downloaded
