"""Video bewerkingspipeline: effecten, overlays en export via MoviePy."""

from pathlib import Path
from typing import Optional

import numpy as np

# Configureer MoviePy om de ingebouwde imageio-ffmpeg binary te gebruiken
# zodat er geen systeem-ffmpeg in PATH nodig is.
try:
    import imageio_ffmpeg
    _ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    if _ffmpeg_exe:
        import moviepy.config as _mp_cfg
        _mp_cfg.FFMPEG_BINARY = _ffmpeg_exe
except Exception:
    pass

from moviepy.editor import (
    AudioFileClip,
    ColorClip,
    CompositeVideoClip,
    ImageClip,
    VideoFileClip,
    concatenate_audioclips,
    concatenate_videoclips,
)
from moviepy.video.fx import fadein, fadeout

from .overlays import (
    make_intro_frame,
    make_player_bar,
    make_score_badge,
    make_thumbnail,
    make_title_overlay,
    make_watermark,
    TARGET_H,
    TARGET_W,
)

# ---------------------------------------------------------------------------
# Clip helpers
# ---------------------------------------------------------------------------


def fit_to_vertical(clip: VideoFileClip) -> VideoFileClip:
    """Schaal en crop een clip naar 1080×1920 (9:16) via cover mode."""
    w, h = clip.size
    scale = max(TARGET_W / w, TARGET_H / h)
    clip = clip.resize(scale)
    x1 = (clip.w - TARGET_W) // 2
    y1 = (clip.h - TARGET_H) // 2
    return clip.crop(x1=x1, y1=y1, width=TARGET_W, height=TARGET_H)


def apply_slow_motion(clip: VideoFileClip, factor: float = 0.5) -> VideoFileClip:
    """Slow-motion door tijdsfactor toe te passen."""
    new_dur = clip.duration / factor
    return clip.fl_time(lambda t: t * factor, apply_to=["mask"]).set_duration(new_dur)


def apply_zoom(clip: VideoFileClip, scale_start: float = 1.0, scale_end: float = 1.12) -> VideoFileClip:
    """Ken-Burns stijl langzame zoom."""
    def zoom(t):
        return scale_start + (scale_end - scale_start) * (t / max(clip.duration, 0.001))
    return clip.resize(zoom)


def make_flash(duration: float = 0.18) -> ColorClip:
    """Witte flash overlay."""
    return (
        ColorClip(size=(TARGET_W, TARGET_H), color=(255, 255, 255))
        .set_duration(duration)
        .set_opacity(0.85)
    )


# ---------------------------------------------------------------------------
# Clip samenstellen
# ---------------------------------------------------------------------------


def build_clip(
    video_path: Path,
    template_cfg: dict,
    global_cfg: dict,
    player_name: str = "",
    club: str = "",
    channel_name: str = "FOOTBALLSHORTS",
    show_title: bool = False,
    title: str = "",
    subtitle: str = "",
    show_score: bool = False,
    team_a: str = "",
    score_a: int = 0,
    score_b: int = 0,
    team_b: str = "",
) -> VideoFileClip:
    """Laad clip, pas effecten toe en voeg overlays toe. Geeft CompositeVideoClip."""

    clip = VideoFileClip(str(video_path))
    clip = fit_to_vertical(clip)

    # Trim
    max_sec = template_cfg.get("clip_trim", 8)
    if clip.duration > max_sec:
        clip = clip.subclip(0, max_sec)

    # Effecten
    if template_cfg.get("slow_motion"):
        factor = global_cfg["effects"]["slow_motion_factor"]
        clip = apply_slow_motion(clip, factor)

    if template_cfg.get("zoom"):
        clip = apply_zoom(clip, scale_end=global_cfg["effects"]["zoom_scale"])

    layers = [clip]

    # Score badge
    if show_score and team_a and team_b:
        badge_arr = make_score_badge(team_a, score_a, score_b, team_b)
        badge = (
            ImageClip(badge_arr, ismask=False)
            .set_duration(clip.duration)
            .set_position(("center", 0))
        )
        layers.append(badge)

    # Spelersnaam balk
    if player_name:
        bar_arr = make_player_bar(
            player_name,
            club,
            accent=global_cfg["text"]["accent_color"],
            primary=global_cfg["text"]["primary_color"],
        )
        bar = (
            ImageClip(bar_arr, ismask=False)
            .set_duration(clip.duration)
            .set_position(("center", TARGET_H - 150))
        )
        layers.append(bar)

    # Titel overlay (alleen laatste clip of als gevraagd)
    if show_title and title:
        pos = template_cfg.get("text_position", "bottom")
        title_arr = make_title_overlay(
            title,
            subtitle=subtitle,
            position=pos,
            accent=global_cfg["text"]["accent_color"],
            primary=global_cfg["text"]["primary_color"],
        )
        show_dur = min(3.5, clip.duration)
        title_clip = (
            ImageClip(title_arr, ismask=False)
            .set_duration(show_dur)
            .set_start(max(0, clip.duration - show_dur))
            .crossfadein(0.3)
        )
        layers.append(title_clip)

    # Watermark
    wm_arr = make_watermark(
        channel_name,
        position=global_cfg["branding"]["watermark_position"],
        accent=global_cfg["text"]["accent_color"],
    )
    wm = (
        ImageClip(wm_arr, ismask=False)
        .set_duration(clip.duration)
    )
    layers.append(wm)

    composed = CompositeVideoClip(layers, size=(TARGET_W, TARGET_H))

    # Flash effect
    if template_cfg.get("flash"):
        flash_dur = global_cfg["effects"]["flash_duration"]
        flash = make_flash(flash_dur)
        composed = CompositeVideoClip([composed, flash], size=(TARGET_W, TARGET_H))

    return composed.set_duration(clip.duration)


# ---------------------------------------------------------------------------
# Intro frame
# ---------------------------------------------------------------------------


def make_intro_clip(channel_name: str, duration: float = 1.5) -> ImageClip:
    """Zwart intro met kanaalbranding."""
    frame = make_intro_frame(channel_name)
    return (
        ImageClip(frame, ismask=False)
        .set_duration(duration)
        .fx(fadeout.fadeout, 0.4)
    )


# ---------------------------------------------------------------------------
# Samenvoegen en exporteren
# ---------------------------------------------------------------------------


def combine_and_export(
    clips: list,
    output_path: Path,
    audio_path: Optional[Path] = None,
    music_volume: float = 0.20,
    max_duration: float = 59.0,
    fps: int = 30,
    crf: int = 23,
    fade_duration: float = 0.25,
    include_intro: bool = True,
    channel_name: str = "FOOTBALLSHORTS",
) -> Path:
    """Voeg clips samen met fades, voeg muziek toe en exporteer als MP4."""
    if not clips:
        raise ValueError("Geen clips om samen te voegen.")

    # Fade in/out per clip
    faded = []
    for c in clips:
        c = fadein.fadein(c, fade_duration)
        c = fadeout.fadeout(c, fade_duration)
        faded.append(c)

    # Intro prependen
    if include_intro:
        intro = make_intro_clip(channel_name, duration=1.5)
        faded = [intro] + faded

    final = concatenate_videoclips(faded, method="compose")

    if final.duration > max_duration:
        final = final.subclip(0, max_duration)

    # Achtergrondmuziek
    if audio_path and audio_path.exists():
        music = AudioFileClip(str(audio_path)).volumex(music_volume)
        if music.duration < final.duration:
            reps = int(final.duration / music.duration) + 1
            music = concatenate_audioclips([music] * reps)
        music = music.subclip(0, final.duration).audio_fadeout(1.5)
        final = final.set_audio(music)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    final.write_videofile(
        str(output_path),
        fps=fps,
        codec="libx264",
        audio_codec="aac",
        preset="fast",
        ffmpeg_params=["-crf", str(crf)],
        logger=None,
    )
    return output_path


def extract_thumbnail_frame(video_path: Path, t: float = 1.5) -> np.ndarray:
    """Trek een frame op tijdstip t uit de video."""
    clip = VideoFileClip(str(video_path))
    clip = fit_to_vertical(clip)
    t = min(t, clip.duration - 0.1)
    frame = clip.get_frame(t)
    clip.close()
    return frame
