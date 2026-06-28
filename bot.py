"""Football Shorts Generator — Telegram bot interface."""

import logging
import os
import sys
import tempfile
from pathlib import Path

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

load_dotenv()
TOKEN = os.environ.get("TELEGRAM_TOKEN", "")

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(message)s",
    level=logging.INFO,
)

TEMPLATES = {
    "skills":      "skill_move",
    "goal":        "goal_celebration",
    "highlights":  "match_highlights",
    "keeper":      "save_of_the_day",
    "spotlight":   "player_spotlight",
    "topskills":   "top_skills",
}

HELP_TEXT = """
⚽ *Football Shorts Generator*

Stuur een commando + YouTube-links om een short te maken:

*Commando's:*
/skills — Skills compilatie (standaard)
/goal — Doelpunt viering
/highlights — Match highlights
/keeper — Keeper redding
/spotlight — Speler spotlight

*Gebruik:*
1. Stuur `/skills Michael Olise | Bayern München`
2. Stuur daarna de YouTube-links (één per bericht of allemaal tegelijk)
3. Stuur /maak als je klaar bent met links sturen

*Voorbeeld (alles in één bericht):*
```
/skills Michael Olise | Bayern München
https://youtu.be/...
https://youtu.be/...
https://youtu.be/...
```

/help — Dit bericht
"""


async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_TEXT, parse_mode="Markdown")


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    name = update.effective_user.first_name or "daar"
    await update.message.reply_text(
        f"Hey {name}! 👋⚽\n\n"
        "Ik maak automatisch Football Shorts van YouTube-clips.\n\n"
        + HELP_TEXT,
        parse_mode="Markdown",
    )


def _parse_header(text: str) -> tuple[str, str, str]:
    """Haal template, speler en club uit de eerste regel."""
    lines = text.strip().splitlines()
    first = lines[0].strip()

    # Commando eraf
    parts = first.split(None, 1)
    cmd = parts[0].lstrip("/").lower()
    rest = parts[1] if len(parts) > 1 else ""

    template = TEMPLATES.get(cmd, "skill_move")

    # "Speler | Club" of alleen "Speler"
    if "|" in rest:
        player, club = [x.strip() for x in rest.split("|", 1)]
    else:
        player, club = rest.strip(), ""

    # URLs in de rest van het bericht
    urls = [l.strip() for l in lines[1:] if l.strip().startswith("http")]
    return template, player, club, urls


async def cmd_template(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Verwerkt /skills, /goal, /highlights, etc."""
    text = update.message.text or ""
    template, player, club, urls = _parse_header(text)

    # Sla sessie op
    ctx.user_data["template"] = template
    ctx.user_data["player"]   = player
    ctx.user_data["club"]     = club
    ctx.user_data["urls"]     = urls

    msg = f"✅ *{template}* ingesteld"
    if player:
        msg += f"\n👤 Speler: {player}"
    if club:
        msg += f"\n🏟️ Club: {club}"
    if urls:
        msg += f"\n🔗 {len(urls)} link(s) ontvangen"
        msg += "\n\nStuur meer links of /maak om te starten."
    else:
        msg += "\n\nStuur nu de YouTube-links (één per bericht)."
        msg += "\nKlaar? Stuur /maak"

    await update.message.reply_text(msg, parse_mode="Markdown")

    if urls:
        await _generate(update, ctx)


async def cmd_maak(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await _generate(update, ctx)


async def handle_url(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Voeg een URL toe aan de huidige sessie."""
    text = (update.message.text or "").strip()
    if not text.startswith("http"):
        return

    ctx.user_data.setdefault("urls", [])
    ctx.user_data.setdefault("template", "skill_move")

    urls = ctx.user_data["urls"]
    urls.append(text)
    count = len(urls)

    await update.message.reply_text(
        f"🔗 Link {count} opgeslagen.\n"
        f"Stuur meer links of /maak om de short te genereren."
    )


async def _generate(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    urls     = ctx.user_data.get("urls", [])
    template = ctx.user_data.get("template", "skill_move")
    player   = ctx.user_data.get("player", "")
    club     = ctx.user_data.get("club", "")

    if not urls:
        await update.message.reply_text(
            "❌ Geen links gevonden. Stuur eerst YouTube-links."
        )
        return

    status_msg = await update.message.reply_text(
        f"⏳ Bezig met genereren…\n"
        f"📥 {len(urls)} clip(s) downloaden en bewerken.\n"
        f"Dit duurt 1–5 minuten, even geduld! ☕"
    )

    try:
        from src.generator import FootballShortsGenerator

        output_dir = Path("output")
        gen = FootballShortsGenerator(output_dir=output_dir)

        await status_msg.edit_text("📥 Clips downloaden…")

        path = gen.generate_short(
            sources=urls,
            template=template,
            player_name=player,
            club=club,
            add_thumbnail=True,
        )

        await status_msg.edit_text("📤 Video uploaden naar Telegram…")

        # Video sturen
        with open(path, "rb") as f:
            caption = f"⚽ *{player or 'Football'} Short*"
            if club:
                caption += f" · {club}"
            await update.message.reply_video(
                video=f,
                caption=caption,
                parse_mode="Markdown",
                supports_streaming=True,
            )

        # Thumbnail sturen als die bestaat
        thumb = path.with_suffix(".jpg")
        if thumb.exists():
            with open(thumb, "rb") as tf:
                await update.message.reply_photo(
                    photo=tf,
                    caption="🖼️ Thumbnail — sla op als omslagfoto"
                )

        await status_msg.delete()

        # Sessie resetten
        ctx.user_data.clear()

    except Exception as exc:
        logging.exception("Generatie mislukt")
        await status_msg.edit_text(
            f"❌ Er ging iets mis:\n`{exc}`\n\n"
            "Controleer of de YouTube-links kloppen en probeer opnieuw.",
            parse_mode="Markdown",
        )


def main():
    if not TOKEN:
        print("FOUT: TELEGRAM_TOKEN niet ingesteld.")
        print("Maak een .env bestand met: TELEGRAM_TOKEN=jouw_token")
        sys.exit(1)

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help",  cmd_help))
    app.add_handler(CommandHandler("maak",  cmd_maak))

    # Template commando's
    for cmd in TEMPLATES:
        app.add_handler(CommandHandler(cmd, cmd_template))

    # URL berichten
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))

    print("⚽ Football Shorts Bot gestart!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
