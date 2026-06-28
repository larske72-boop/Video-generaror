"""Download voetbal clips via yt-dlp (YouTube, Twitter/X, Instagram, etc.)."""

import subprocess
import sys
from pathlib import Path


def _get_ffmpeg_path() -> str | None:
    """Geef pad naar imageio-ffmpeg binary, of None als niet gevonden."""
    try:
        import imageio_ffmpeg
        path = imageio_ffmpeg.get_ffmpeg_exe()
        if path:
            return path
    except Exception:
        pass
    return None


def _build_args(output_template: str) -> list[str]:
    """Bouw yt-dlp argumenten op met automatische ffmpeg-detectie."""
    ffmpeg_path = _get_ffmpeg_path()

    args = [
        sys.executable, "-m", "yt_dlp",
        "--output", output_template,
        "--no-playlist",
        "--no-warnings",
    ]

    if ffmpeg_path:
        # ffmpeg beschikbaar: download beste kwaliteit en merge
        args += [
            "--ffmpeg-location", ffmpeg_path,
            "--format", "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=1080]+bestaudio/best[height<=1080]",
            "--merge-output-format", "mp4",
        ]
    else:
        # Geen ffmpeg: download voorgemengd mp4 (iets lagere kwaliteit maar werkt altijd)
        args += [
            "--format", "best[height<=1080][ext=mp4]/best[height<=1080]/best",
        ]

    return args


def download_clip(
    url: str,
    dest_dir: Path,
    filename: str = "clip_%(autonumber)s",
    **_kwargs,
) -> list[Path]:
    """Download één URL naar dest_dir, geeft lijst van gedownloade paden terug."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    template = str(dest_dir / f"{filename}.%(ext)s")

    args = _build_args(template)
    args.append(url)

    print(f"  Downloaden: {url}", flush=True)
    result = subprocess.run(args, capture_output=True, text=True)

    # Zoek alle video-bestanden in de map
    found = (
        sorted(dest_dir.glob("*.mp4"))
        + sorted(dest_dir.glob("*.webm"))
        + sorted(dest_dir.glob("*.mkv"))
    )

    if result.returncode != 0 and not found:
        msg = (result.stderr.strip() or result.stdout.strip()
               or "Onbekende fout — controleer of de video publiek beschikbaar is")
        raise RuntimeError(f"Download mislukt:\n{msg}")

    if not found:
        raise RuntimeError(
            "yt-dlp klaar maar geen bestand gevonden. "
            "Mogelijk is de video privé, leeftijdsbeperkt of verwijderd."
        )

    print(f"  ✓ Gedownload: {found[0].name}", flush=True)
    return found


def download_clips(
    urls: list[str],
    dest_dir: Path,
    **_kwargs,
) -> list[Path]:
    """Download meerdere URLs, geeft alle gedownloade paden terug."""
    all_paths: list[Path] = []
    for i, url in enumerate(urls):
        clip_dir = dest_dir / f"clip_{i:02d}"
        try:
            paths = download_clip(url, dest_dir=clip_dir)
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
