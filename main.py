#!/usr/bin/env python3
"""
Football Shorts Generator
CLI voor het automatisch genereren van voetbal YouTube Shorts
via Higgsfield AI.
"""

import os
import sys
from pathlib import Path

import click
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

load_dotenv()
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
@click.version_option("1.0.0", prog_name="football-shorts")
def cli():
    """⚽ Football Shorts Generator - Maak virale voetbal YouTube Shorts met AI."""
    pass


@cli.command("generate")
@click.option(
    "--template", "-t",
    type=click.Choice(TEMPLATES),
    default="goal_celebration",
    show_default=True,
    help="Video stijl template",
)
@click.option("--player", "-p", default="", help="Naam van de speler (bijv. 'Messi')")
@click.option("--club", "-c", default="", help="Naam van de club (bijv. 'Barcelona')")
@click.option("--title", default="", help="Eigen titel (anders wordt er een gegenereerd)")
@click.option("--prompt", default="", help="Eigen AI video prompt (optioneel)")
@click.option("--clips", "-n", default=None, type=int, help="Aantal AI clips om te genereren")
@click.option("--no-slow-mo", is_flag=True, default=False, help="Slow motion uitschakelen")
@click.option("--no-flash", is_flag=True, default=False, help="Flash effect uitschakelen")
@click.option("--no-thumbnail", is_flag=True, default=False, help="Thumbnail overslaan")
@click.option("--output-dir", "-o", default="./output", help="Map voor output bestanden")
@click.option("--api-key", envvar="HIGGSFIELD_API_KEY", help="Higgsfield API key")
@click.option("--config", default=None, help="Pad naar config.yaml")
def generate_cmd(
    template, player, club, title, prompt, clips, no_slow_mo, no_flash,
    no_thumbnail, output_dir, api_key, config,
):
    """Genereer een football short video."""
    from src.generator import FootballShortsGenerator

    try:
        gen = FootballShortsGenerator(
            api_key=api_key,
            config_path=Path(config) if config else None,
            output_dir=Path(output_dir),
        )
        path = gen.generate_short(
            template=template,
            player_name=player,
            club=club,
            custom_title=title,
            custom_prompt=prompt,
            num_clips=clips,
            slow_motion=not no_slow_mo if not no_slow_mo else False,
            flash=not no_flash if not no_flash else False,
            add_thumbnail=not no_thumbnail,
        )
        console.print(f"\n[bold green]Klaar![/bold green] Video opgeslagen: {path}")
    except ValueError as e:
        console.print(f"[red]Fout:[/red] {e}")
        sys.exit(1)
    except RuntimeError as e:
        console.print(f"[red]Generatie mislukt:[/red] {e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Onverwachte fout:[/red] {e}")
        raise


@cli.command("batch")
@click.option(
    "--template", "-t",
    type=click.Choice(TEMPLATES),
    default="goal_celebration",
    show_default=True,
)
@click.option("--count", "-n", default=3, show_default=True, help="Aantal shorts om te genereren")
@click.option("--players", default="", help="Komma-gescheiden lijst van spelersnamen")
@click.option("--output-dir", "-o", default="./output")
@click.option("--api-key", envvar="HIGGSFIELD_API_KEY")
@click.option("--config", default=None)
def batch_cmd(template, count, players, output_dir, api_key, config):
    """Genereer meerdere football shorts in een batch."""
    from src.generator import FootballShortsGenerator

    player_list = [p.strip() for p in players.split(",") if p.strip()] if players else []

    try:
        gen = FootballShortsGenerator(
            api_key=api_key,
            config_path=Path(config) if config else None,
            output_dir=Path(output_dir),
        )
        paths = gen.batch_generate(
            template=template,
            count=count,
            player_names=player_list or None,
        )
        console.print(f"\n[bold green]Batch klaar![/bold green] {len(paths)}/{count} shorts gegenereerd.")
        for p in paths:
            console.print(f"  • {p}")
    except Exception as e:
        console.print(f"[red]Fout:[/red] {e}")
        sys.exit(1)


@cli.command("list-templates")
def list_templates_cmd():
    """Toon alle beschikbare video templates."""
    import yaml
    config_path = Path(__file__).parent / "config.yaml"
    with open(config_path) as f:
        config = yaml.safe_load(f)

    table = Table(title="Beschikbare Football Shorts Templates", border_style="yellow")
    table.add_column("Template", style="cyan", no_wrap=True)
    table.add_column("Clips", justify="center")
    table.add_column("Slow-Mo", justify="center")
    table.add_column("Flash", justify="center")
    table.add_column("Muziekstijl", style="green")

    for name, tmpl in config["templates"].items():
        table.add_row(
            name,
            str(tmpl["clips"]),
            "✓" if tmpl["slow_motion"] else "✗",
            "✓" if tmpl["flash"] else "✗",
            tmpl["music_style"],
        )

    console.print(table)


@cli.command("check-balance")
@click.option("--api-key", envvar="HIGGSFIELD_API_KEY")
def check_balance_cmd(api_key):
    """Controleer je Higgsfield credit saldo."""
    from src.higgsfield_client import HiggsFieldClient
    try:
        client = HiggsFieldClient(api_key=api_key)
        resp = client.session.get(f"{client.BASE_URL}/v1/balance", timeout=10)
        resp.raise_for_status()
        data = resp.json()
        credits = data.get("credits", data.get("balance", "onbekend"))
        console.print(f"[bold]Higgsfield credits:[/bold] [green]{credits}[/green]")
    except Exception as e:
        console.print(f"[red]Saldo ophalen mislukt:[/red] {e}")


if __name__ == "__main__":
    cli()
