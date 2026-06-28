"""PIL-gebaseerde tekst- en grafische overlays voor football shorts."""

from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

TARGET_W, TARGET_H = 1080, 1920

# ---------------------------------------------------------------------------
# Font helpers
# ---------------------------------------------------------------------------

FONT_CANDIDATES = [
    # Windows
    "C:/Windows/Fonts/impact.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/arial.ttf",
    # macOS
    "/System/Library/Fonts/Supplemental/Impact.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    # Linux
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
    # Bundled assets
    "assets/fonts/Impact.ttf",
    "assets/fonts/BebasNeue-Regular.ttf",
]


def load_font(size: int) -> ImageFont.FreeTypeFont:
    for path in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


# ---------------------------------------------------------------------------
# Teken helpers
# ---------------------------------------------------------------------------

def draw_text_centered(
    draw: ImageDraw.Draw,
    text: str,
    cx: int,
    cy: int,
    font: ImageFont.FreeTypeFont,
    fill: str = "#FFFFFF",
    shadow: str = "#000000",
    stroke_width: int = 3,
) -> None:
    """Teken tekst gecentreerd op (cx, cy) met schaduw/rand."""
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    x = cx - tw // 2
    y = cy - th // 2

    # Schaduw iteraties
    for dx in range(-stroke_width, stroke_width + 1):
        for dy in range(-stroke_width, stroke_width + 1):
            if abs(dx) + abs(dy) > 0:
                draw.text((x + dx, y + dy), text, font=font, fill=shadow)
    draw.text((x, y), text, font=font, fill=fill)


def draw_text_left(
    draw: ImageDraw.Draw,
    text: str,
    x: int,
    cy: int,
    font: ImageFont.FreeTypeFont,
    fill: str = "#FFFFFF",
    shadow: str = "#000000",
    stroke_width: int = 2,
) -> None:
    """Teken tekst links-uitgelijnd op (x, cy)."""
    bbox = draw.textbbox((0, 0), text, font=font)
    th = bbox[3] - bbox[1]
    y = cy - th // 2
    for dx in range(-stroke_width, stroke_width + 1):
        for dy in range(-stroke_width, stroke_width + 1):
            if abs(dx) + abs(dy) > 0:
                draw.text((x + dx, y + dy), text, font=font, fill=shadow)
    draw.text((x, y), text, font=font, fill=fill)


# ---------------------------------------------------------------------------
# Overlay frames als numpy arrays
# ---------------------------------------------------------------------------

def make_title_overlay(
    title: str,
    subtitle: str = "",
    position: str = "bottom",
    width: int = TARGET_W,
    height: int = TARGET_H,
    accent: str = "#FFD700",
    primary: str = "#FFFFFF",
) -> np.ndarray:
    """Grotere titeltekst met optionele ondertitel, geeft RGBA numpy array."""
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    font_title = load_font(80)
    font_sub = load_font(50)

    if position == "bottom":
        cy_title = height - 200
        cy_sub = height - 120
    else:
        cy_title = 160
        cy_sub = 230

    draw_text_centered(draw, title, width // 2, cy_title, font_title, fill=accent)
    if subtitle:
        draw_text_centered(draw, subtitle, width // 2, cy_sub, font_sub, fill=primary)

    return np.array(img)


def make_player_bar(
    player_name: str,
    club: str = "",
    width: int = TARGET_W,
    accent: str = "#FFD700",
    primary: str = "#FFFFFF",
) -> np.ndarray:
    """Halfransparante balk onderaan met naam + club, geeft RGBA array."""
    bar_h = 150
    img = Image.new("RGBA", (width, bar_h), (0, 0, 0, 0))

    # Gradient achtergrond
    bg = Image.new("RGBA", (width, bar_h), (0, 0, 0, 0))
    for y in range(bar_h):
        alpha = int(185 * (y / bar_h))
        for x in range(width):
            bg.putpixel((x, y), (0, 0, 0, alpha))
    img = Image.alpha_composite(img, bg)

    draw = ImageDraw.Draw(img)
    font_name = load_font(58)
    font_club = load_font(36)

    draw_text_centered(draw, player_name.upper(), width // 2, 52, font_name, fill=primary)
    if club:
        draw_text_centered(draw, club, width // 2, 110, font_club, fill=accent)

    return np.array(img)


def make_watermark(
    channel_name: str,
    position: str = "top-left",
    width: int = TARGET_W,
    height: int = TARGET_H,
    accent: str = "#FFD700",
) -> np.ndarray:
    """Klein kanaallogo op de gewenste positie."""
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = load_font(34)
    label = f"@{channel_name.replace(' ', '').lower()}"

    pad = 18
    if position == "top-left":
        x, cy = pad + 10, pad + 20
        draw_text_left(draw, label, x, cy, font, fill=accent, stroke_width=2)
    elif position == "top-right":
        bbox = draw.textbbox((0, 0), label, font=font)
        tw = bbox[2] - bbox[0]
        x = width - tw - pad - 10
        draw_text_left(draw, label, x, pad + 20, font, fill=accent, stroke_width=2)

    return np.array(img)


def make_score_badge(
    team_a: str,
    score_a: int,
    score_b: int,
    team_b: str,
    width: int = TARGET_W,
    accent: str = "#FFD700",
    primary: str = "#FFFFFF",
) -> np.ndarray:
    """Score badge bovenaan voor wedstrijd highlights."""
    badge_h = 100
    img = Image.new("RGBA", (width, badge_h), (0, 0, 0, 180))
    draw = ImageDraw.Draw(img)

    font_score = load_font(60)
    font_team = load_font(30)

    score_txt = f"{score_a} - {score_b}"
    draw_text_centered(draw, score_txt, width // 2, badge_h // 2, font_score, fill=accent)
    draw_text_centered(draw, team_a.upper(), width // 4, badge_h // 2, font_team, fill=primary)
    draw_text_centered(draw, team_b.upper(), 3 * width // 4, badge_h // 2, font_team, fill=primary)

    return np.array(img)


def make_intro_frame(
    channel_name: str,
    width: int = TARGET_W,
    height: int = TARGET_H,
    accent: str = "#FFD700",
) -> np.ndarray:
    """Zwart intro frame met kanaalbranding."""
    img = Image.new("RGBA", (width, height), (0, 0, 0, 255))
    draw = ImageDraw.Draw(img)

    font_big = load_font(96)
    font_sub = load_font(44)

    draw_text_centered(draw, "⚽", width // 2, height // 2 - 80, font_big, fill=accent)
    draw_text_centered(draw, channel_name.upper(), width // 2, height // 2 + 20, font_big, fill=accent)
    draw_text_centered(draw, "FOOTBALL SHORTS", width // 2, height // 2 + 110, font_sub, fill="#FFFFFF")

    return np.array(img)


# ---------------------------------------------------------------------------
# Thumbnail
# ---------------------------------------------------------------------------

def make_thumbnail(
    frame: np.ndarray,
    title: str,
    output_path: Path,
    accent: str = "#FFD700",
    primary: str = "#FFFFFF",
) -> Path:
    """Maak een YouTube-thumbnail van een video frame met grote titel."""
    img = Image.fromarray(frame).convert("RGBA")

    # Donkere gradient onderaan
    grad = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw_g = ImageDraw.Draw(grad)
    for i in range(350):
        alpha = int(210 * (i / 350))
        draw_g.rectangle(
            [(0, img.height - 350 + i), (img.width, img.height - 350 + i + 1)],
            fill=(0, 0, 0, alpha),
        )
    blended = Image.alpha_composite(img, grad)

    draw = ImageDraw.Draw(blended)
    font = load_font(95)
    draw_text_centered(draw, title, img.width // 2, img.height - 110, font, fill=accent)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    blended.convert("RGB").save(str(output_path), "JPEG", quality=95)
    return output_path
