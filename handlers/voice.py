import logging
from telegram import Update
from telegram.ext import ContextTypes

import database as db
from services.voice_recognition import process_voice_message
from utils.keyboards import strength_keyboard

logger = logging.getLogger(__name__)


async def voice_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle incoming voice messages.
    Transcribes speech → extracts player name → adds to DB.
    """
    chat_id = update.effective_chat.id
    voice = update.message.voice

    # Notify user that processing has started
    processing_msg = await update.message.reply_text(
        "🎙 Розпізнаю голосове повідомлення…"
    )

    try:
        name = await process_voice_message(context.bot, voice.file_id)
    except Exception as e:
        logger.error("Voice handler error: %s", e)
        await processing_msg.edit_text(
            "❌ Помилка обробки голосу. Спробуйте ще раз або введіть ім'я текстом:\n"
            "`/add_player Іванець`",
            parse_mode="Markdown",
        )
        return

    if not name:
        await processing_msg.edit_text(
            "🤔 Не вдалося розпізнати ім'я гравця.\n\n"
            "Спробуйте сказати: _«Додай Іванця»_ або _«Гравець Петро»_\n"
            "Або введіть текстом: `/add_player Ім'я`",
            parse_mode="Markdown",
        )
        return

    # Check for duplicate
    if db.player_exists(name, chat_id):
        await processing_msg.edit_text(
            f"⚠️ Гравець *{name}* вже є у списку.",
            parse_mode="Markdown",
        )
        return

    player_id = db.add_player(name, chat_id)
    await processing_msg.edit_text(
        f"✅ Гравець *{name}* доданий! (ID: {player_id})\n"
        f"Встановіть рівень сили:",
        parse_mode="Markdown",
        reply_markup=strength_keyboard(player_id),
    )
