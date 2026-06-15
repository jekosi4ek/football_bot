import logging
from telegram import Update
from telegram.ext import ContextTypes

import database as db
from services.team_divider import divide_players, format_teams_message
from utils.keyboards import main_menu_keyboard, teams_count_keyboard

logger = logging.getLogger(__name__)


# ── /create_team ──────────────────────────────────────────────────────────────

async def create_team_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manually create a named empty team."""
    args = context.args
    chat_id = update.effective_chat.id

    if not args:
        await update.message.reply_text(
            "✏️ Введіть назву команди:\n`/create_team Зірки`",
            parse_mode="Markdown",
        )
        return

    name = " ".join(args).strip()
    db.save_teams(
        db.get_teams(chat_id) + [{"name": name, "player_ids": []}],
        chat_id,
    )
    await update.message.reply_text(
        f"✅ Команда *{name}* створена.",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(),
    )


# ── /auto_divide ──────────────────────────────────────────────────────────────

async def auto_divide_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    players = db.get_players(chat_id)

    if len(players) < 2:
        await update.message.reply_text(
            "⚠️ Потрібно мінімум *2 гравці* для розподілу.\n"
            "Додайте гравців: /add\\_player",
            parse_mode="Markdown",
        )
        return

    # If a number is passed directly, divide immediately
    if context.args:
        try:
            num = int(context.args[0])
            await _do_divide(update, chat_id, players, num)
            return
        except ValueError:
            pass

    await update.message.reply_text(
        f"⚽ Гравців: *{len(players)}*\n\nНа скільки команд ділити?",
        parse_mode="Markdown",
        reply_markup=teams_count_keyboard(),
    )


async def _do_divide(update_or_query, chat_id: int, players: list[dict], num_teams: int):
    """Perform the division and display results."""
    if num_teams > len(players):
        num_teams = len(players)

    teams = divide_players(players, num_teams)
    db.save_teams(
        [{"name": t["name"], "player_ids": t["player_ids"]} for t in teams],
        chat_id,
    )

    msg = format_teams_message(teams, players)

    # Works for both Message and CallbackQuery contexts
    if hasattr(update_or_query, "message"):
        await update_or_query.message.reply_text(
            msg, parse_mode="Markdown", reply_markup=main_menu_keyboard()
        )
    else:
        await update_or_query.edit_message_text(
            msg, parse_mode="Markdown", reply_markup=main_menu_keyboard()
        )

    return teams


# ── /show_teams ───────────────────────────────────────────────────────────────

async def show_teams_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    teams = db.get_teams(chat_id)
    players = db.get_players(chat_id)

    if not teams:
        await update.message.reply_text(
            "👥 Команди ще не сформовані.\n\nВикористайте /auto\\_divide",
            parse_mode="Markdown",
        )
        return

    msg = format_teams_message(teams, players)
    await update.message.reply_text(
        msg, parse_mode="Markdown", reply_markup=main_menu_keyboard()
    )
