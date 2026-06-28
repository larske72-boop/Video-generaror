"""Video bewerkingspipeline met MoviePy + PIL voor football shorts."""

import random
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import (
    VideoFileClip,
    ImageClip,
    TextClip,
    CompositeVideoClip,
    concatenate_videoclips,
    AudioFileClip,
    ColorClip,
)
from moviepy.video.fx import fadein, fadeout
from rich.console import Console

console = Console()

TARGET_W, TARGET_H = 1080, 1920  # 9:16 vertical


def _fit_clip(clip: VideoFileClip, target_w: int = TARGET_W, target_h: int = TARGET_H) -> VideoFileClip:
    """Schaal en crop clip naar doelresolutie (cover mode)."""
    w, h = clip.size
    scale = max(target_w / w, target_h / h)
    clip = clip.resize(scale)
    x1 = (clip.w - target_w) // 2
    y1 = (clip.h - target_h) // 2
    return clip.crop(x1=x1, y1=y1, width=target_w, height=target_h)


def _slow_motion(clip: VideoFileClip, factor: float = 0.5) -> VideoFileClip:
    """Pas slow motion toe door tijdsnelheid te halveren."""
    return clip.fx(lambda c: c.fl_time(lambda t: t * factor)).set_duration(clip.duration / factor)


def _zoom_effect(clip: VideoFileClip, scale_start: float = 1.0, scale_end: float = 1.12) -> VideoFileClip:
    """Ken-Burns stijl langzame zoom in/uit."""
    def zoom(t):
        factor = scale_start + (scale_end - scale_start) * (t / clip.duration)
        return factor

    return clip.resize(lambda t: zoom(t))


def _flash_overlay(duration: float = 0.15) -> ImageClip:
    """Witte flash overlay van korte duur."""
    return ColorClip(size=(TARGET_W, TARGET_H), color=(255, 255, 255)).set_duration(duration).set_opacity(0.85)


def _make_title_frame(
    text: str,
    subtitle: str = "",
    width: int = TARGET_W,
    height: int = TARGET_H,
    bg_alpha: int = 0,
) -> np.ndarray:
    """Render tekst op transparante achtergrond via PIL, geeft numpy array terug."""
    img = Image.new("RGBA", (width, height), (0, 0, 0, bg_alpha))
    draw = ImageDraw.Draw(img)

    # Probeer een systeem lettertype te laden
    font_large = _load_font(80)
    font_small = _load_font(48)

    # Hoofdtekst met schaduw
    _draw_text_shadow(draw, text, width // 2, height - 280, font_large, fill="#FFD700", shadow="#000000")
    if subtitle:
        _draw_text_shadow(draw, subtitle, width // 2, height - 180, font_small, fill="#FFFFFF", shadow="#000000")

    return np.array(img)


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    """Laad een vet lettertype als dat beschikbaar is."""
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
        "/System/Library/Fonts/Supplemental/Impact.ttf",
        "Impact.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def _draw_text_shadow(
    draw: ImageDraw.Draw,
    text: str,
    cx: int,
    cy: int,
    font: ImageFont.FreeTypeFont,
    fill: str = "#FFD700",
    shadow: str = "#000000",
    stroke_width: int = 3,
) -> None:
    """Teken tekst gecentreerd met schaduwrand."""
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    x = cx - tw // 2
    y = cy - th // 2

    # Schaduw
    for dx in range(-stroke_width, stroke_width + 1):
        for dy in range(-stroke_width, stroke_width + 1):
            if dx != 0 or dy != 0:
                draw.text((x + dx, y + dy), text, font=font, fill=shadow)
    # Hoofdtekst
    draw.text((x, y), text, font=font, fill=fill)


def _make_player_label(player_name: str, club: str = "", width: int = TARGET_W) -> np.ndarray:
    """Maak een spelersnaam label onderaan in beeld."""
    height = 160
    img = Image.new("RGBA", (width, height), (0, 0, 0, 160))
    draw = ImageDraw.Draw(img)
    font_name = _load_font(56)
    font_club = _load_font(36)
    _draw_text_shadow(draw, player_name.upper(), width // 2, 55, font_name, fill="#FFFFFF")
    if club:
        _draw_text_shadow(draw, club, width // 2, 120, font_club, fill="#FFD700")
    return np.array(img)


def _make_watermark(channel_name: str, width: int = TARGET_W) -> np.ndarray:
    """Maak een klein kanaallogo linksboven."""
    height = 70
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = _load_font(36)
    _draw_text_shadow(draw, f"@{channel_name}", 20 + 120, 35, font, fill="#FFD700")
    return np.array(img)


# ---------------------------------------------------------------------------
# Hoofd bewerkingsfuncties
# ---------------------------------------------------------------------------

def create_clip_with_overlays(
    video_path: Path,
    title: str,
    subtitle: str = "",
    player_name: str = "",
    club: str = "",
    channel_name: str = "FOOTBALLSHORTS",
    slow_mo: bool = False,
    zoom: bool = True,
    flash: bool = False,
    max_duration: float = 8.0,
) -> VideoFileClip:
    """Laad een clip, pas effecten toe en voeg overlays toe."""
    clip = VideoFileClip(str(video_path))
    clip = _fit_clip(clip)

    # Duur begrenzen
    if clip.duration > max_duration:
        clip = clip.subclip(0, max_duration)

    # Slow motion
    if slow_mo:
        clip = _slow_motion(clip, factor=0.5)

    # Zoom-in effect
    if zoom:
        clip = _zoom_effect(clip)

    layers = [clip]

    # Spelersnaam overlay onderaan
    if player_name:
        label_arr = _make_player_label(player_name, club)
        label = (
            ImageClip(label_arr, ismask=False)
            .set_duration(clip.duration)
            .set_position(("center", TARGET_H - 160))
        )
        layers.append(label)

    # Titel overlay
    if title:
        title_arr = _make_title_frame(title, subtitle)
        title_clip = (
            ImageClip(title_arr, ismask=False)
            .set_duration(min(3.0, clip.duration))
            .set_start(max(0, clip.duration - 3.5))
        )
        layers.append(title_clip)

    # Watermark
    wm_arr = _make_watermark(channel_name)
    wm = (
        ImageClip(wm_arr, ismask=False)
        .set_duration(clip.duration)
        .set_position((10, 40))
    )
    layers.append(wm)

    composed = CompositeVideoClip(layers, size=(TARGET_W, TARGET_H))

    # Flash effect aan het begin
    if flash:
        flash_clip = _flash_overlay(0.2).set_start(0)
        composed = CompositeVideoClip([composed, flash_clip], size=(TARGET_W, TARGET_H))

    return composed.set_duration(clip.duration)


def build_short(
    clips: list[VideoFileClip],
    output_path: Path,
    audio_path: Optional[Path] = None,
    max_duration: float = 59.0,
    fps: int = 30,
) -> Path:
    """Combineer clips tot een YouTube Short en exporteer als MP4."""
    if not clips:
        raise ValueError("Geen clips om te combineren")

    # Clips samenvoegen met fade overgang
    faded = []
    for i, c in enumerate(clips):
        c = fadein.fadein(c, 0.2)
        c = fadeout.fadeout(c, 0.2)
        faded.append(c)

    final = concatenate_videoclips(faded, method="compose")

    # Duur beperken
    if final.duration > max_duration:
        final = final.subclip(0, max_duration)

    # Achtergrondmuziek toevoegen als die beschikbaar is
    if audio_path and audio_path.exists():
        music = AudioFileClip(str(audio_path)).volumex(0.25)
        if music.duration < final.duration:
            loops = int(final.duration / music.duration) + 1
            from moviepy.editor import concatenate_audioclips
            music = concatenate_audioclips([music] * loops)
        music = music.subclip(0, final.duration)
        final = final.set_audio(music)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    final.write_videofile(
        str(output_path),
        fps=fps,
        codec="libx264",
        audio_codec="aac",
        preset="fast",
        ffmpeg_params=["-crf", "23"],
        logger=None,
    )
    return output_path


def create_thumbnail(
    video_path: Path,
    title: str,
    output_path: Path,
    timestamp: float = 1.0,
) -> Path:
    """Trek een frame uit de video en voeg thumbnail-tekst toe."""
    clip = VideoFileClip(str(video_path))
    clip = _fit_clip(clip)
    t = min(timestamp, clip.duration - 0.1)
    frame = clip.get_frame(t)
    clip.close()

    img = Image.fromarray(frame)

    # Donkere gradient onderin
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for i in range(300):
        alpha = int(180 * (i / 300))
        draw.rectangle([(0, img.height - 300 + i), (img.width, img.height - 300 + i + 1)], fill=(0, 0, 0, alpha))

    combined = Image.alpha_composite(img.convert("RGBA"), overlay)
    draw2 = ImageDraw.Draw(combined)
    font = _load_font(90)
    _draw_text_shadow(draw2, title, img.width // 2, img.height - 120, font, fill="#FFD700")

    combined.convert("RGB").save(str(output_path), "JPEG", quality=95)
    return output_path
