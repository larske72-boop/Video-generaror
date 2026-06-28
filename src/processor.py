"""Direct ffmpeg video processing — geen MoviePy vereist."""

import subprocess
import tempfile
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image

TARGET_W, TARGET_H = 1080, 1920
_FFMPEG_EXE: Optional[str] = None


def _ffmpeg() -> str:
    global _FFMPEG_EXE
    if _FFMPEG_EXE is None:
        try:
            import imageio_ffmpeg
            exe = imageio_ffmpeg.get_ffmpeg_exe()
            _FFMPEG_EXE = str(exe) if exe else "ffmpeg"
        except Exception:
            _FFMPEG_EXE = "ffmpeg"
    return _FFMPEG_EXE


def _run(args: list, check: bool = True) -> subprocess.CompletedProcess:
    cmd = [_ffmpeg(), "-y"] + [str(a) for a in args]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if check and result.returncode != 0:
        err = (result.stderr or result.stdout or "onbekende ffmpeg fout")[-3000:]
        raise RuntimeError(err)
    return result


def _save_png(arr: np.ndarray, path: Path) -> None:
    Image.fromarray(arr.astype(np.uint8), mode="RGBA").save(str(path), "PNG")


# ─────────────────────────────────────────────────────────────────────────────
# Intro clip
# ─────────────────────────────────────────────────────────────────────────────

def make_intro_video(channel_name: str, output: Path, duration: float = 1.5) -> Path:
    """Zwart intro-frame als korte video (video-only, geen audio)."""
    from .overlays import make_intro_frame
    with tempfile.TemporaryDirectory() as tmp:
        img_path = Path(tmp) / "intro.png"
        _save_png(make_intro_frame(channel_name), img_path)
        _run([
            "-loop", "1", "-i", str(img_path),
            "-t", str(duration),
            "-vf", f"scale={TARGET_W}:{TARGET_H},format=yuv420p",
            "-r", "30",
            "-c:v", "libx264", "-preset", "fast",
            "-an",
            str(output),
        ])
    return output


# ─────────────────────────────────────────────────────────────────────────────
# Per-clip verwerking
# ─────────────────────────────────────────────────────────────────────────────

def process_clip(
    input_path: Path,
    output_path: Path,
    trim_sec: float = 8.0,
    slow_motion: bool = False,
    player_name: str = "",
    club: str = "",
    channel_name: str = "FOOTBALLSHORTS",
    show_title: bool = False,
    title: str = "",
    subtitle: str = "",
    accent: str = "#FFD700",
    primary: str = "#FFFFFF",
) -> Path:
    """
    Trim clip, crop naar 9:16 (1080×1920), voeg overlays toe.
    Output is video-only MP4 (geen audio — muziek wordt bij concat toegevoegd).
    """
    from .overlays import make_player_bar, make_watermark, make_title_overlay

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)

        # ── Overlay PNGs maken en opslaan ──────────────────────────────
        wm_png = tmp / "wm.png"
        _save_png(make_watermark(channel_name, accent=accent), wm_png)

        bar_png: Optional[Path] = None
        if player_name:
            bar_png = tmp / "bar.png"
            _save_png(make_player_bar(player_name, club, accent=accent, primary=primary), bar_png)

        title_png: Optional[Path] = None
        if show_title and title:
            title_png = tmp / "title.png"
            _save_png(make_title_overlay(title, subtitle=subtitle, accent=accent, primary=primary), title_png)

        # ── Input argumenten opbouwen ──────────────────────────────────
        inputs = ["-t", str(trim_sec), "-i", str(input_path), "-i", str(wm_png)]
        bar_idx: Optional[int] = None
        title_idx: Optional[int] = None
        next_idx = 2

        if bar_png:
            inputs += ["-i", str(bar_png)]
            bar_idx = next_idx
            next_idx += 1

        if title_png:
            inputs += ["-i", str(title_png)]
            title_idx = next_idx

        # ── Filter complex opbouwen ────────────────────────────────────
        slow = ",setpts=2.0*PTS" if slow_motion else ""
        fc = (
            f"[0:v]scale={TARGET_W}:{TARGET_H}:force_original_aspect_ratio=increase,"
            f"crop={TARGET_W}:{TARGET_H}{slow}[base]"
        )
        cur = "base"

        # Watermark: volledig transparant frame eroverheen
        fc += f";[{cur}][1:v]overlay=0:0[ov1]"
        cur = "ov1"

        # Spelersbalk: gepositioneerd 150px vanaf onderkant
        if bar_idx is not None:
            lbl = f"ov{bar_idx}"
            fc += f";[{cur}][{bar_idx}:v]overlay=0:{TARGET_H - 150}[{lbl}]"
            cur = lbl

        # Titel overlay: volledig frame eroverheen
        if title_idx is not None:
            lbl = f"ov{title_idx}"
            fc += f";[{cur}][{title_idx}:v]overlay=0:0[{lbl}]"
            cur = lbl

        # ── ffmpeg uitvoeren ───────────────────────────────────────────
        _run(inputs + [
            "-filter_complex", fc,
            "-map", f"[{cur}]",
            "-an",
            "-r", "30",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-pix_fmt", "yuv420p",
            str(output_path),
        ])

    return output_path


# ─────────────────────────────────────────────────────────────────────────────
# Samenvoegen en exporteren
# ─────────────────────────────────────────────────────────────────────────────

def concat_and_export(
    clip_paths: list[Path],
    output_path: Path,
    intro_path: Optional[Path] = None,
    max_duration: float = 59.0,
    music_path: Optional[Path] = None,
    music_volume: float = 0.20,
) -> Path:
    """Voeg alle clips samen en voeg optioneel muziek toe."""
    all_clips = []
    if intro_path and intro_path.exists():
        all_clips.append(intro_path)
    all_clips.extend(p for p in clip_paths if p.exists())

    if not all_clips:
        raise RuntimeError("Geen clips om samen te voegen.")

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)

        # Concat list (forward slashes werken ook op Windows)
        list_path = tmp / "concat.txt"
        with open(list_path, "w", encoding="utf-8") as f:
            for p in all_clips:
                f.write(f"file '{p.as_posix()}'\n")

        # Stap 1: Concat alle video clips naar tussenbestand
        concat_tmp = tmp / "concat_raw.mp4"
        _run([
            "-f", "concat", "-safe", "0", "-i", str(list_path),
            "-t", str(max_duration),
            "-c:v", "libx264", "-preset", "fast", "-crf", "22",
            "-pix_fmt", "yuv420p",
            "-an",
            str(concat_tmp),
        ])

        # Stap 2: Muziek toevoegen (optioneel)
        if music_path and Path(music_path).exists():
            _run([
                "-i", str(concat_tmp),
                "-stream_loop", "-1", "-i", str(music_path),
                "-t", str(max_duration),
                "-filter_complex", f"[1:a]volume={music_volume}[aout]",
                "-map", "0:v",
                "-map", "[aout]",
                "-c:v", "copy",
                "-c:a", "aac", "-ar", "44100",
                str(output_path),
            ])
        else:
            # Geen muziek: kopieer direct
            import shutil
            shutil.copy2(str(concat_tmp), str(output_path))

    return output_path


# ─────────────────────────────────────────────────────────────────────────────
# Thumbnail frame extractie
# ─────────────────────────────────────────────────────────────────────────────

def extract_frame(video_path: Path, t: float = 2.0) -> np.ndarray:
    """Trek een RGB frame op tijdstip t uit de video."""
    with tempfile.TemporaryDirectory() as tmp:
        frame_path = Path(tmp) / "frame.png"
        # Probeer op tijdstip t
        _run(["-ss", str(t), "-i", str(video_path), "-vframes", "1", str(frame_path)], check=False)
        if not frame_path.exists():
            # Fallback: eerste frame
            _run(["-i", str(video_path), "-vframes", "1", str(frame_path)], check=False)
        if frame_path.exists():
            return np.array(Image.open(frame_path).convert("RGB"))
    return np.zeros((TARGET_H, TARGET_W, 3), dtype=np.uint8)
