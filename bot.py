"""
Football Manager Telegram Bot
Entry point — registers all handlers and starts polling.
"""

import logging
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

from config import BOT_TOKEN
from database import init_db
from handlers.players import (
    start_handler,
    add_player_handler,
    list_players_handler,
    remove_player_handler,
    set_strength_handler,
)
from handlers.teams import (
    create_team_handler,
    auto_divide_handler,
    show_teams_handler,
)
from handlers.match import (
    start_match_handler,
    pause_timer_handler,
    resume_timer_handler,
    stop_match_handler,
)
from handlers.voice import voice_message_handler
from handlers.callbacks import callback_handler

logging.basicConfig(
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def main():
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        raise RuntimeError(
            "Set BOT_TOKEN in your .env file or as an environment variable!"
        )

    init_db()

    app = Application.builder().token(BOT_TOKEN).build()

    # ── Player commands ───────────────────────────────────────────────────────
    app.add_handler(CommandHandler("start",         start_handler))
    app.add_handler(CommandHandler("add_player",    add_player_handler))
    app.add_handler(CommandHandler("list_players",  list_players_handler))
    app.add_handler(CommandHandler("remove_player", remove_player_handler))
    app.add_handler(CommandHandler("set_strength",  set_strength_handler))

    # ── Team commands ─────────────────────────────────────────────────────────
    app.add_handler(CommandHandler("create_team",   create_team_handler))
    app.add_handler(CommandHandler("auto_divide",   auto_divide_handler))
    app.add_handler(CommandHandler("show_teams",    show_teams_handler))

    # ── Match / timer commands ────────────────────────────────────────────────
    app.add_handler(CommandHandler("start_match",   start_match_handler))
    app.add_handler(CommandHandler("pause_timer",   pause_timer_handler))
    app.add_handler(CommandHandler("resume_timer",  resume_timer_handler))
    app.add_handler(CommandHandler("stop_match",    stop_match_handler))

    # ── Voice messages ────────────────────────────────────────────────────────
    app.add_handler(MessageHandler(filters.VOICE, voice_message_handler))

    # ── Inline keyboard callbacks ─────────────────────────────────────────────
    app.add_handler(CallbackQueryHandler(callback_handler))

    logger.info("Bot is running. Press Ctrl-C to stop.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
