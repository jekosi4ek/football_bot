import logging
from telegram import Update
from telegram.ext import ContextTypes

import database as db
from services.voice_recognition import process_voice_raw, extract_player_name
from services.tournament import parse_match_and_score
from utils.keyboards import strength_keyboard

logger = logging.getLogger(__name__)


async def voice_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    voice = update.message.voice

    processing_msg = await update.message.reply_text("🎙 Розпізнаю голосове повідомлення…")

    try:
        text = await process_voice_raw(context.bot, voice.file_id)
    except Exception as e:
        logger.error("Voice handler error: %s", e)
        await processing_msg.edit_text(
            "❌ Помилка обробки голосу. Спробуйте ще раз або введіть текстом."
        )
        return

    if not text:
        await processing_msg.edit_text(
            "🤔 Не вдалося розпізнати мову.\n\n"
            "Скажіть: _«Додай Іванця»_ або _«матч 1 три один»_",
            parse_mode="Markdown",
        )
        return

    # ── 1. Try tournament score: "матч 2 три один" ────────────────────────────
    score_result = parse_match_and_score(text)
    if score_result:
        match_num, s1, s2 = score_result
        matches = db.get_tournament(chat_id)
        target = next((m for m in matches if m["match_order"] == match_num), None)
        if target:
            db.update_match_score(target["id"], s1, s2, chat_id)
            from services.tournament import format_schedule, format_standings
            from handlers.tournament import _tournament_keyboard
            matches = db.get_tournament(chat_id)
            teams = db.get_teams(chat_id)
            team_names = [t["name"] for t in teams]
            out = format_schedule(matches) + "\n\n" + format_standings(team_names, matches)
            await processing_msg.edit_text(
                f"⚽ Рахунок збережено: Матч {match_num} — *{s1}:{s2}*\n\n{out}",
                parse_mode="Markdown",
                reply_markup=_tournament_keyboard(matches),
            )
            return

    # ── 2. Try player name: "Додай Іванця" ───────────────────────────────────
    name = extract_player_name(text)
    if not name:
        await processing_msg.edit_text(
            f"🤔 Почув: _{text}_\n\n"
            "Не вдалося розпізнати команду.\n"
            "Спробуйте: _«Додай Іванця»_, _«матч 1 три один»_\n"
            "Або введіть текстом: `/add_player Ім'я`",
            parse_mode="Markdown",
        )
        return

    if db.player_exists(name, chat_id):
        await processing_msg.edit_text(
            f"⚠️ Гравець *{name}* вже є у списку.", parse_mode="Markdown"
        )
        return

    player_id = db.add_player(name, chat_id)
    await processing_msg.edit_text(
        f"✅ Гравець *{name}* доданий!\nВстановіть рівень сили:",
        parse_mode="Markdown",
        reply_markup=strength_keyboard(player_id),
    )
