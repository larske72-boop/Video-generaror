#!/usr/bin/env python3
"""
⚽ Football Shorts Generator
Maak automatisch virale voetbal YouTube Shorts van clips of YouTube-links.
Geen externe AI-API nodig.
"""

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

console = Console()

TEMPLATES = [
    "goal_celebration",
    "skill_move",
    "match_highlights",
    "player_spotlight",
    "save_of_the_day",
    "top_skills",
]


@click.group()
@click.version_option("2.0.0", prog_name="football-shorts")
def cli():
    """⚽ Football Shorts Generator — Maak virale voetbal YouTube Shorts."""
    pass


# ---------------------------------------------------------------------------
# generate
# ---------------------------------------------------------------------------

@cli.command("generate")
@click.argument("sources", nargs=-1, required=True)
@click.option(
    "--template", "-t",
    type=click.Choice(TEMPLATES),
    default="goal_celebration",
    show_default=True,
    help="Video stijl template",
)
@click.option("--player", "-p", default="", help="Spelersnaam (bijv. 'Messi')")
@click.option("--club", "-c", default="", help="Clubnaam (bijv. 'Barcelona')")
@click.option("--title", default="", help="Eigen titel (anders pakt hij de template-standaard)")
@click.option("--music", "-m", default=None, type=click.Path(exists=True), help="Pad naar muziekbestand (.mp3/.wav)")
@click.option("--no-thumbnail", is_flag=True, help="Thumbnail overslaan")
@click.option("--output-dir", "-o", default="./output", show_default=True, help="Output map")
@click.option("--config", default=None, type=click.Path(exists=True), help="Eigen config.yaml")
# Wedstrijd score opties (alleen relevant bij match_highlights)
@click.option("--team-a", default="", help="Thuisteam naam")
@click.option("--score-a", default=0, type=int, help="Thuisteam doelpunten")
@click.option("--score-b", default=0, type=int, help="Uitteam doelpunten")
@click.option("--team-b", default="", help="Uitteam naam")
def generate_cmd(
    sources, template, player, club, title, music,
    no_thumbnail, output_dir, config,
    team_a, score_a, score_b, team_b,
):
    """Genereer een football short van lokale bestanden of YouTube-URLs.

    SOURCES kunnen zijn:
      - Paden naar lokale videobestanden (.mp4, .mov, ...)
      - YouTube-URLs (of andere yt-dlp-compatibele URLs)
      - Een combinatie van beide

    \b
    Voorbeelden:
      python main.py generate clip1.mp4 clip2.mp4 -t goal_celebration -p "Messi"
      python main.py generate "https://youtu.be/..." -t skill_move -p "Neymar" -c "Al-Hilal"
      python main.py generate "https://youtu.be/..." clip.mp4 -t match_highlights --team-a PSG --score-a 3 --score-b 1 --team-b Real
    """
    from src.generator import FootballShortsGenerator

    try:
        gen = FootballShortsGenerator(
            config_path=Path(config) if config else None,
            output_dir=Path(output_dir),
        )
        path = gen.generate_short(
            sources=list(sources),
            template=template,
            player_name=player,
            club=club,
            title=title,
            music_path=Path(music) if music else None,
            add_thumbnail=not no_thumbnail,
            team_a=team_a,
            score_a=score_a,
            score_b=score_b,
            team_b=team_b,
        )
        console.print(f"\n[bold green]Klaar![/bold green] Opgeslagen als: [cyan]{path}[/cyan]")

    except ValueError as exc:
        console.print(f"[red]Configuratiefout:[/red] {exc}")
        sys.exit(1)
    except RuntimeError as exc:
        console.print(f"[red]Generatie mislukt:[/red] {exc}")
        sys.exit(1)


# ---------------------------------------------------------------------------
# batch
# ---------------------------------------------------------------------------

@cli.command("batch")
@click.argument("urls_file", type=click.Path(exists=True))
@click.option(
    "--template", "-t",
    type=click.Choice(TEMPLATES),
    default="goal_celebration",
    show_default=True,
)
@click.option("--clips-per-short", default=3, show_default=True, help="Aantal clips per short")
@click.option("--player", "-p", default="")
@click.option("--club", "-c", default="")
@click.option("--music", "-m", default=None, type=click.Path(exists=True))
@click.option("--output-dir", "-o", default="./output")
@click.option("--config", default=None, type=click.Path(exists=True))
def batch_cmd(urls_file, template, clips_per_short, player, club, music, output_dir, config):
    """Genereer meerdere shorts vanuit een tekstbestand met URLs (één per regel).

    \b
    Voorbeeld urls.txt:
      https://youtu.be/abc123
      https://youtu.be/def456
      # dit is een commentaar
      https://youtu.be/ghi789
    """
    from src.generator import FootballShortsGenerator

    try:
        gen = FootballShortsGenerator(
            config_path=Path(config) if config else None,
            output_dir=Path(output_dir),
        )
        paths = gen.batch_from_file(
            urls_file=Path(urls_file),
            clips_per_short=clips_per_short,
            template=template,
            player_name=player,
            club=club,
            music_path=Path(music) if music else None,
        )
        console.print(f"\n[bold green]Batch klaar![/bold green] {len(paths)} short(s) gemaakt.")
        for p in paths:
            console.print(f"  • {p}")
    except Exception as exc:
        console.print(f"[red]Fout:[/red] {exc}")
        sys.exit(1)


# ---------------------------------------------------------------------------
# list-templates
# ---------------------------------------------------------------------------

@cli.command("list-templates")
def list_templates_cmd():
    """Toon alle beschikbare video templates."""
    import yaml
    with open(Path(__file__).parent / "config.yaml") as f:
        cfg = yaml.safe_load(f)

    table = Table(
        title="⚽ Football Shorts Templates",
        border_style="yellow",
        show_lines=True,
    )
    table.add_column("Template", style="cyan", no_wrap=True)
    table.add_column("Label", style="white")
    table.add_column("Clips trim", justify="center")
    table.add_column("Slow-Mo", justify="center")
    table.add_column("Flash", justify="center")
    table.add_column("Zoom", justify="center")
    table.add_column("Standaard titel")

    for name, t in cfg["templates"].items():
        table.add_row(
            name,
            t["label"],
            f"{t['clip_trim']}s",
            "[green]✓[/green]" if t["slow_motion"] else "[dim]✗[/dim]",
            "[green]✓[/green]" if t["flash"] else "[dim]✗[/dim]",
            "[green]✓[/green]" if t["zoom"] else "[dim]✗[/dim]",
            t["title"],
        )
    console.print(table)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    cli()
