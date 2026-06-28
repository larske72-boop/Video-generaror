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


def _paste_rgba(base: np.ndarray, overlay: np.ndarray, ox: int, oy: int) -> None:
    """Alpha-composite RGBA overlay onto RGB base array in-place (numpy, fast)."""
    oh, ow = overlay.shape[:2]
    bh, bw = base.shape[:2]
    x0 = max(0, ox)
    y0 = max(0, oy)
    sx0 = x0 - ox
    sy0 = y0 - oy
    x1 = min(bw, ox + ow)
    y1 = min(bh, oy + oh)
    if x0 >= x1 or y0 >= y1:
        return
    sx1 = sx0 + (x1 - x0)
    sy1 = sy0 + (y1 - y0)
    src = overlay[sy0:sy1, sx0:sx1].astype(np.float32)
    alpha = src[:, :, 3:4] / 255.0
    dst = base[y0:y1, x0:x1].astype(np.float32)
    base[y0:y1, x0:x1] = (dst * (1.0 - alpha) + src[:, :, :3] * alpha).astype(np.uint8)


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
# Player tracking helpers
# ─────────────────────────────────────────────────────────────────────────────

def _detect_player_positions(
    video_path: Path,
    trim_sec: float,
    orig_w: int,
    orig_h: int,
) -> list[tuple[float, float]]:
    """
    Background subtraction (MOG2) at reduced resolution to find the main
    motion blob per frame.  Returns per-frame (cx, cy) in original-video
    pixel coordinates.  Requires opencv-python-headless.
    """
    import cv2

    DETECT_W = 320
    scale = DETECT_W / orig_w
    detect_h = int(orig_h * scale)

    cap = cv2.VideoCapture(str(video_path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    max_frames = int(trim_sec * fps)

    subtractor = cv2.createBackgroundSubtractorMOG2(
        history=25, varThreshold=36, detectShadows=False
    )
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    warmup = min(12, max(1, max_frames // 5))

    raw: list[Optional[tuple[float, float]]] = []
    for i in range(max_frames):
        ret, frame = cap.read()
        if not ret:
            break
        small = cv2.resize(frame, (DETECT_W, detect_h))
        mask = subtractor.apply(small)

        if i < warmup:
            raw.append(None)
            continue

        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        pos: Optional[tuple[float, float]] = None
        if contours:
            # Pick contour whose centroid is closest to horizontal center
            cx_mid = DETECT_W / 2
            best = min(
                contours,
                key=lambda c: (
                    abs((cv2.moments(c)["m10"] / (cv2.moments(c)["m00"] + 1e-9)) - cx_mid)
                    if cv2.contourArea(c) > 80
                    else 1e9
                ),
            )
            if cv2.contourArea(best) > 80:
                M = cv2.moments(best)
                if M["m00"] > 0:
                    pos = (
                        (M["m10"] / M["m00"]) / scale,
                        (M["m01"] / M["m00"]) / scale,
                    )
        raw.append(pos)

    cap.release()

    # Forward-fill then backward-fill None entries
    default = (float(orig_w / 2), float(orig_h * 0.55))
    filled: list[Optional[tuple[float, float]]] = []
    last: Optional[tuple[float, float]] = None
    for p in raw:
        if p is not None:
            last = p
        filled.append(last)

    first_valid = next((p for p in filled if p is not None), default)
    return [p if p is not None else first_valid for p in filled]


def _smooth_positions(
    positions: list[tuple[float, float]],
    window: int = 11,
) -> list[tuple[float, float]]:
    """Moving-average smoothing of (x, y) trajectory."""
    if len(positions) < 2:
        return positions
    xs = np.array([p[0] for p in positions], dtype=np.float32)
    ys = np.array([p[1] for p in positions], dtype=np.float32)
    k = np.ones(window, dtype=np.float32) / window
    xs_s = np.convolve(xs, k, mode="same")
    ys_s = np.convolve(ys, k, mode="same")
    return list(zip(xs_s.tolist(), ys_s.tolist()))


# ─────────────────────────────────────────────────────────────────────────────
# Frame-by-frame rendering with tracked arrow (requires opencv)
# ─────────────────────────────────────────────────────────────────────────────

def _process_with_tracking(
    input_path: Path,
    output_path: Path,
    trim_sec: float,
    slow_motion: bool,
    player_name: str,
    club: str,
    channel_name: str,
    show_title: bool,
    title: str,
    subtitle: str,
    accent: str,
    primary: str,
) -> Path:
    """
    Two-pass render:
      1. Background-subtraction pass → per-frame player positions.
      2. Frame-by-frame: scale+crop to 9:16, composite overlays at tracked
         position, pipe raw RGB to ffmpeg for libx264 encoding.
    """
    import cv2
    from .overlays import make_player_bar, make_watermark, make_title_overlay, make_arrow_indicator

    ARROW_W, ARROW_H = 80, 120
    # Arrow tip points this many px above the detected player centroid
    ARROW_OFFSET = 130

    # ── Video metadata ─────────────────────────────────────────────────────
    cap = cv2.VideoCapture(str(input_path))
    fps_in = cap.get(cv2.CAP_PROP_FPS) or 30.0
    orig_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    orig_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    if orig_w == 0 or orig_h == 0:
        raise RuntimeError(f"Onleesbare videodimensies: {input_path}")

    # ── Scale/crop geometry (mirrors ffmpeg scale+crop filter) ─────────────
    s = max(TARGET_W / orig_w, TARGET_H / orig_h)
    scaled_w = int(orig_w * s)
    scaled_h = int(orig_h * s)
    x_off = (scaled_w - TARGET_W) // 2
    y_off = (scaled_h - TARGET_H) // 2

    # ── Pass 1: detect + smooth player trajectory ──────────────────────────
    raw_pos = _detect_player_positions(input_path, trim_sec, orig_w, orig_h)
    if not raw_pos:
        raise RuntimeError("Geen frames gedetecteerd in eerste pass.")
    positions = _smooth_positions(raw_pos, window=11)

    # ── Pre-render all overlay arrays (done once, reused per frame) ────────
    wm_arr    = make_watermark(channel_name, accent=accent)
    bar_arr   = make_player_bar(player_name, club, accent=accent, primary=primary) if player_name else None
    title_arr = (
        make_title_overlay(title, subtitle=subtitle, accent=accent, primary=primary)
        if (show_title and title) else None
    )
    arrow_arr = make_arrow_indicator(ARROW_W, ARROW_H, accent=accent)

    # ── Start ffmpeg stdin-pipe encoder ───────────────────────────────────
    fps_out = 30
    repeat  = 2 if slow_motion else 1   # duplicate frames for 0.5× slow-mo

    ff = _ffmpeg()
    proc = subprocess.Popen(
        [
            ff, "-y",
            "-f", "rawvideo", "-vcodec", "rawvideo",
            "-s", f"{TARGET_W}x{TARGET_H}",
            "-pix_fmt", "rgb24",
            "-r", str(fps_out),
            "-i", "pipe:0",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-pix_fmt", "yuv420p",
            "-an",
            str(output_path),
        ],
        stdin=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    try:
        cap = cv2.VideoCapture(str(input_path))
        max_frames = int(trim_sec * fps_in)

        for frame_idx in range(max_frames):
            ret, bgr = cap.read()
            if not ret:
                break

            # Scale + center-crop to 9:16 (fast C++ path)
            scaled  = cv2.resize(bgr, (scaled_w, scaled_h), interpolation=cv2.INTER_LINEAR)
            cropped = scaled[y_off: y_off + TARGET_H, x_off: x_off + TARGET_W]
            frame   = cv2.cvtColor(cropped, cv2.COLOR_BGR2RGB).copy()

            # Static full-frame overlays
            _paste_rgba(frame, wm_arr, 0, 0)
            if bar_arr is not None:
                _paste_rgba(frame, bar_arr, 0, TARGET_H - 150)
            if title_arr is not None:
                _paste_rgba(frame, title_arr, 0, 0)

            # Arrow at tracked position
            pos_idx = min(frame_idx, len(positions) - 1)
            cx_o, cy_o = positions[pos_idx]
            # Map from original-video coords → cropped-9:16 coords
            cx_c = cx_o * s - x_off
            cy_c = cy_o * s - y_off
            # Tip of the arrow is ARROW_OFFSET px above detected centroid
            tip_y = cy_c - ARROW_OFFSET
            ax = int(cx_c - ARROW_W / 2)
            ay = int(tip_y - ARROW_H)
            _paste_rgba(frame, arrow_arr, ax, ay)

            raw_bytes = frame.tobytes()
            for _ in range(repeat):
                proc.stdin.write(raw_bytes)

        cap.release()
    except Exception:
        proc.kill()
        raise
    finally:
        try:
            proc.stdin.close()
        except OSError:
            pass

    proc.wait()
    if proc.returncode != 0:
        err = (proc.stderr.read() or b"")[-2000:].decode("utf-8", errors="replace")
        raise RuntimeError(f"ffmpeg encoding fout: {err}")

    return output_path


# ─────────────────────────────────────────────────────────────────────────────
# Pure-ffmpeg clip processing (no opencv — static arrow position)
# ─────────────────────────────────────────────────────────────────────────────

def _process_clip_ffmpeg(
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
    """Trim, crop 9:16, overlays — static arrow at center-frame position."""
    from .overlays import make_player_bar, make_watermark, make_title_overlay, make_arrow_indicator

    ARROW_W, ARROW_H = 80, 120
    ARROW_TIP_Y  = int(TARGET_H * 0.52)
    ARROW_BASE_Y = ARROW_TIP_Y - ARROW_H
    ARROW_X      = TARGET_W // 2 - ARROW_W // 2

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)

        wm_png = tmp / "wm.png"
        _save_png(make_watermark(channel_name, accent=accent), wm_png)

        bar_png: Optional[Path] = None
        if player_name:
            bar_png = tmp / "bar.png"
            _save_png(make_player_bar(player_name, club, accent=accent, primary=primary), bar_png)

        arrow_png: Optional[Path] = None
        if player_name:
            arrow_png = tmp / "arrow.png"
            _save_png(make_arrow_indicator(ARROW_W, ARROW_H, accent=accent), arrow_png)

        title_png: Optional[Path] = None
        if show_title and title:
            title_png = tmp / "title.png"
            _save_png(make_title_overlay(title, subtitle=subtitle, accent=accent, primary=primary), title_png)

        inputs = ["-t", str(trim_sec), "-i", str(input_path), "-i", str(wm_png)]
        bar_idx: Optional[int]   = None
        arrow_idx: Optional[int] = None
        title_idx: Optional[int] = None
        next_idx = 2

        if bar_png:
            inputs += ["-i", str(bar_png)]
            bar_idx = next_idx; next_idx += 1
        if arrow_png:
            inputs += ["-i", str(arrow_png)]
            arrow_idx = next_idx; next_idx += 1
        if title_png:
            inputs += ["-i", str(title_png)]
            title_idx = next_idx

        slow = ",setpts=2.0*PTS" if slow_motion else ""
        fc = (
            f"[0:v]scale={TARGET_W}:{TARGET_H}:force_original_aspect_ratio=increase,"
            f"crop={TARGET_W}:{TARGET_H}{slow}[base]"
        )
        cur = "base"

        fc += f";[{cur}][1:v]overlay=0:0[ov1]"
        cur = "ov1"

        if bar_idx is not None:
            lbl = f"ov{bar_idx}"
            fc += f";[{cur}][{bar_idx}:v]overlay=0:{TARGET_H - 150}[{lbl}]"
            cur = lbl

        if arrow_idx is not None:
            lbl = f"ov{arrow_idx}"
            bob = f"{ARROW_BASE_Y}+15*sin(2*PI*1.5*t)"
            fc += f";[{cur}][{arrow_idx}:v]overlay=x={ARROW_X}:y={bob}[{lbl}]"
            cur = lbl

        if title_idx is not None:
            lbl = f"ov{title_idx}"
            fc += f";[{cur}][{title_idx}:v]overlay=0:0[{lbl}]"
            cur = lbl

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
# Public entry point
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
    Als player_name opgegeven én opencv beschikbaar: gevolgd pijltje boven speler.
    Anders: statisch pijltje via pure ffmpeg.
    Output is video-only MP4 (geen audio).
    """
    if player_name:
        try:
            import cv2  # noqa: F401
            return _process_with_tracking(
                input_path, output_path, trim_sec, slow_motion,
                player_name, club, channel_name, show_title, title, subtitle,
                accent, primary,
            )
        except ImportError:
            pass  # opencv niet geinstalleerd — val terug op ffmpeg
        except Exception as exc:
            import traceback
            print(f"  ⚠ Tracking mislukt ({exc}), statisch pijltje gebruikt", flush=True)
            traceback.print_exc()

    return _process_clip_ffmpeg(
        input_path, output_path, trim_sec, slow_motion,
        player_name, club, channel_name, show_title, title, subtitle,
        accent, primary,
    )


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

        list_path = tmp / "concat.txt"
        with open(list_path, "w", encoding="utf-8") as f:
            for p in all_clips:
                abs_posix = Path(p).resolve().as_posix()
                f.write(f"file '{abs_posix}'\n")

        concat_tmp = tmp / "concat_raw.mp4"
        _run([
            "-f", "concat", "-safe", "0", "-i", str(list_path),
            "-t", str(max_duration),
            "-c:v", "libx264", "-preset", "fast", "-crf", "22",
            "-pix_fmt", "yuv420p",
            "-an",
            str(concat_tmp),
        ])

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
        _run(["-ss", str(t), "-i", str(video_path), "-vframes", "1", str(frame_path)], check=False)
        if not frame_path.exists():
            _run(["-i", str(video_path), "-vframes", "1", str(frame_path)], check=False)
        if frame_path.exists():
            return np.array(Image.open(frame_path).convert("RGB"))
    return np.zeros((TARGET_H, TARGET_W, 3), dtype=np.uint8)
