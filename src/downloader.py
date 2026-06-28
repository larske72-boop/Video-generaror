"""Download voetbal clips via yt-dlp (YouTube, Twitter/X, Instagram, etc.)."""

import subprocess
import sys
from pathlib import Path


def _ydl_base_args(quality: str, merge_format: str, output_template: str) -> list[str]:
    return [
        sys.executable, "-m", "yt_dlp",
        "--format", quality,
        "--merge-output-format", merge_format,
        "--output", output_template,
        "--no-playlist",
        "--quiet",
        "--no-warnings",
    ]


def download_clip(
    url: str,
    dest_dir: Path,
    filename: str = "clip_%(autonumber)s",
    quality: str = "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
    merge_format: str = "mp4",
    max_duration: int = 120,
) -> list[Path]:
    """Download één URL naar dest_dir, geeft lijst van gedownloade paden terug."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    template = str(dest_dir / f"{filename}.%(ext)s")

    args = _ydl_base_args(quality, merge_format, template)
    args.append(url)

    print(f"  Downloaden: {url}", flush=True)
    result = subprocess.run(args, capture_output=True, text=True)

    if result.returncode != 0:
        msg = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"Download mislukt voor {url}:\n{msg}")

    found = sorted(dest_dir.glob("*.mp4")) + sorted(dest_dir.glob("*.webm")) + sorted(dest_dir.glob("*.mkv"))
    if not found:
        msg = result.stderr.strip() or result.stdout.strip() or "Onbekende fout (video mogelijk privé of niet beschikbaar)"
        raise RuntimeError(f"Download mislukt voor {url}:\n{msg}")
    return found


def download_clips(
    urls: list[str],
    dest_dir: Path,
    quality: str = "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
    merge_format: str = "mp4",
    max_duration: int = 120,
) -> list[Path]:
    """Download meerdere URLs, geeft alle gedownloade paden terug."""
    all_paths: list[Path] = []
    for i, url in enumerate(urls):
        clip_dir = dest_dir / f"clip_{i:02d}"
        try:
            paths = download_clip(
                url,
                dest_dir=clip_dir,
                quality=quality,
                merge_format=merge_format,
                max_duration=max_duration,
            )
            all_paths.extend(paths)
            print(f"  ✓ Download {i + 1}/{len(urls)} klaar", flush=True)
        except RuntimeError as e:
            print(f"  ✗ URL {i + 1} mislukt: {e}", flush=True)

    return all_paths


def load_urls_from_file(path: Path) -> list[str]:
    """Laad URL-lijst uit een tekstbestand (één URL per regel, # = commentaar)."""
    urls = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                urls.append(line)
    return urls
