"""Hoofd orkestratie pipeline voor football shorts generatie."""

import random
import time
from pathlib import Path
from typing import Optional

import yaml
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

from .higgsfield_client import HiggsFieldClient
from .video_editor import create_clip_with_overlays, build_short, create_thumbnail
from .prompts import FOOTBALL_PROMPTS, TITLES, THUMBNAIL_PROMPTS

console = Console()

DEFAULT_CONFIG = Path(__file__).parent.parent / "config.yaml"


def load_config(config_path: Optional[Path] = None) -> dict:
    path = config_path or DEFAULT_CONFIG
    with open(path) as f:
        return yaml.safe_load(f)


class FootballShortsGenerator:
    def __init__(
        self,
        api_key: Optional[str] = None,
        config_path: Optional[Path] = None,
        output_dir: Optional[Path] = None,
    ):
        self.config = load_config(config_path)
        self.client = HiggsFieldClient(api_key=api_key)
        self.output_dir = output_dir or Path(self.config["output"]["output_dir"])
        self.output_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------

    def generate_short(
        self,
        template: str = "goal_celebration",
        player_name: str = "",
        club: str = "",
        custom_title: str = "",
        custom_prompt: str = "",
        num_clips: Optional[int] = None,
        slow_motion: Optional[bool] = None,
        flash: Optional[bool] = None,
        add_thumbnail: bool = True,
    ) -> Path:
        """Genereer een complete football short video."""

        tmpl = self.config["templates"].get(template)
        if not tmpl:
            raise ValueError(f"Onbekend template '{template}'. Kies uit: {list(self.config['templates'].keys())}")

        clips_count = num_clips or tmpl["clips"]
        use_slow_mo = slow_motion if slow_motion is not None else tmpl["slow_motion"]
        use_flash = flash if flash is not None else tmpl["flash"]

        title = custom_title or random.choice(TITLES.get(template, ["FOOTBALL! ⚽"]))
        subtitle = ""
        if player_name:
            subtitle = f"{player_name}" + (f" | {club}" if club else "")

        timestamp = int(time.time())
        job_dir = self.output_dir / f"{template}_{timestamp}"
        job_dir.mkdir(parents=True, exist_ok=True)

        console.print(Panel(
            f"[bold yellow]Football Shorts Generator[/bold yellow]\n"
            f"Template: [cyan]{template}[/cyan] | Clips: [cyan]{clips_count}[/cyan]\n"
            f"Slow-mo: [cyan]{use_slow_mo}[/cyan] | Flash: [cyan]{use_flash}[/cyan]\n"
            f"Titel: [cyan]{title}[/cyan]",
            border_style="yellow",
        ))

        # ------- Stap 1: AI video clips genereren -------
        console.print("\n[bold]Stap 1:[/bold] AI video clips genereren via Higgsfield...")

        prompts = FOOTBALL_PROMPTS.get(template, FOOTBALL_PROMPTS["goal_celebration"])
        if custom_prompt:
            prompts = [custom_prompt] + prompts

        video_model = self.config["higgsfield"]["default_model"]
        clip_duration = self.config["higgsfield"]["clip_duration"]
        aspect_ratio = "9:16"

        downloaded_clips = []
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            transient=True,
            console=console,
        ) as progress:
            task = progress.add_task("Clips genereren...", total=clips_count)
            for i in range(clips_count):
                prompt = prompts[i % len(prompts)]
                if player_name:
                    prompt = f"{prompt}, featuring {player_name}"
                clip_path = job_dir / f"clip_{i:02d}.mp4"
                try:
                    self.client.generate_and_download_video(
                        prompt=prompt,
                        dest_path=clip_path,
                        model=video_model,
                        duration=clip_duration,
                        aspect_ratio=aspect_ratio,
                    )
                    downloaded_clips.append(clip_path)
                    progress.advance(task)
                    console.print(f"  [green]✓[/green] Clip {i + 1}/{clips_count} klaar")
                except Exception as e:
                    console.print(f"  [red]✗[/red] Clip {i + 1} mislukt: {e}")

        if not downloaded_clips:
            raise RuntimeError("Geen enkele clip kon worden gegenereerd. Controleer je API key en credits.")

        # ------- Stap 2: Clips bewerken -------
        console.print("\n[bold]Stap 2:[/bold] Effecten en overlays toepassen...")

        channel_name = self.config["branding"]["channel_name"].replace(" ", "")
        edited_clips = []
        for i, clip_path in enumerate(downloaded_clips):
            console.print(f"  Bewerken clip {i + 1}/{len(downloaded_clips)}...")
            try:
                edited = create_clip_with_overlays(
                    video_path=clip_path,
                    title=title if i == len(downloaded_clips) - 1 else "",
                    subtitle=subtitle if i == len(downloaded_clips) - 1 else "",
                    player_name=player_name if i > 0 else "",
                    club=club,
                    channel_name=channel_name,
                    slow_mo=use_slow_mo,
                    zoom=True,
                    flash=use_flash and i == 0,
                )
                edited_clips.append(edited)
            except Exception as e:
                console.print(f"  [red]✗[/red] Bewerken mislukt: {e}")

        if not edited_clips:
            raise RuntimeError("Geen clips konden worden bewerkt.")

        # ------- Stap 3: Combineren en exporteren -------
        console.print("\n[bold]Stap 3:[/bold] Clips samenvoegen en exporteren...")

        output_name = f"{template}_{player_name.replace(' ', '_') or 'short'}_{timestamp}.mp4"
        output_path = self.output_dir / output_name

        max_dur = self.config["output"]["max_duration"]
        fps = self.config["output"]["fps"]

        build_short(
            clips=edited_clips,
            output_path=output_path,
            max_duration=max_dur,
            fps=fps,
        )

        # Resources vrijgeven
        for c in edited_clips:
            try:
                c.close()
            except Exception:
                pass

        # ------- Stap 4: Thumbnail -------
        if add_thumbnail:
            console.print("\n[bold]Stap 4:[/bold] Thumbnail genereren...")
            thumb_path = output_path.with_suffix(".jpg")
            try:
                create_thumbnail(output_path, title, thumb_path, timestamp=1.5)
                console.print(f"  [green]✓[/green] Thumbnail: {thumb_path}")
            except Exception as e:
                console.print(f"  [yellow]⚠[/yellow] Thumbnail mislukt: {e}")

        console.print(Panel(
            f"[bold green]✓ Short klaar![/bold green]\n"
            f"Bestand: [cyan]{output_path}[/cyan]\n"
            f"Duur: [cyan]{max_dur}s max[/cyan] | Formaat: [cyan]9:16 (1080×1920)[/cyan]",
            border_style="green",
        ))

        return output_path

    # ------------------------------------------------------------------

    def batch_generate(
        self,
        template: str,
        count: int = 3,
        player_names: Optional[list] = None,
        **kwargs,
    ) -> list[Path]:
        """Genereer meerdere shorts in een batch."""
        results = []
        for i in range(count):
            console.print(f"\n[bold magenta]═══ Short {i + 1}/{count} ═══[/bold magenta]")
            player = (player_names[i % len(player_names)] if player_names else "")
            try:
                path = self.generate_short(template=template, player_name=player, **kwargs)
                results.append(path)
            except Exception as e:
                console.print(f"[red]Short {i + 1} mislukt: {e}[/red]")
        return results
