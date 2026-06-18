import logging
from telegram import Update
from telegram.ext import ContextTypes

import database as db
from handlers.session import get_session_players
from services.team_divider import divide_players, format_teams_message, _md
from utils.keyboards import main_menu_keyboard, teams_count_keyboard, after_divide_keyboard, teams_action_keyboard

logger = logging.getLogger(__name__)


async def create_team_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    chat_id = update.effective_chat.id
    if not args:
        await update.message.reply_text(
            "✏️ Введіть назву команди:\n`/create_team Зірки`",
            parse_mode="Markdown",
        )
        return
    name = " ".join(args).strip()
    db.save_teams(db.get_teams(chat_id) + [{"name": name, "player_ids": []}], chat_id)
    await update.message.reply_text(
        f"✅ Команда *{name}* створена.",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(),
    )


async def auto_divide_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    all_players = db.get_players(chat_id)
    players = get_session_players(chat_id, all_players)

    if len(players) < 2:
        await update.message.reply_text(
            "⚠️ Потрібно мінімум *2 гравці* для розподілу.\n"
            "Додайте гравців або налаштуйте сесію: /game",
            parse_mode="Markdown",
        )
        return

    if context.args:
        try:
            num = int(context.args[0])
            await _do_divide(update, chat_id, players, num)
            return
        except ValueError:
            pass

    session_note = (
        f"_Сесія: {len(players)} з {len(all_players)} гравців_\n\n"
        if len(players) != len(all_players) else ""
    )
    await update.message.reply_text(
        f"{session_note}⚽ Гравців сьогодні: *{len(players)}*\n\nНа скільки команд ділити?",
        parse_mode="Markdown",
        reply_markup=teams_count_keyboard(),
    )


async def _do_divide(update_or_query, chat_id: int, players: list[dict], num_teams: int):
    if num_teams > len(players):
        num_teams = len(players)

    teams = divide_players(players, num_teams)
    db.save_teams([{"name": t["name"], "player_ids": t["player_ids"]} for t in teams], chat_id)

    msg = format_teams_message(teams, players)
    kb = after_divide_keyboard()

    if hasattr(update_or_query, "message"):
        await update_or_query.message.reply_text(msg, parse_mode="Markdown", reply_markup=kb)
    else:
        await update_or_query.edit_message_text(msg, parse_mode="Markdown", reply_markup=kb)
    return teams


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
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=teams_action_keyboard())


async def pending_rename_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    old_name = context.chat_data.get("waiting_rename")
    if not old_name:
        return

    new_name = update.message.text.strip()
    if not new_name or len(new_name) > 30:
        await update.message.reply_text("⚠️ Назва має бути 1–30 символів. Спробуйте ще:")
        return

    del context.chat_data["waiting_rename"]
    db.rename_team(chat_id, old_name, new_name)

    teams = db.get_teams(chat_id)
    players = db.get_players(chat_id)
    msg = format_teams_message(teams, players)
    await update.message.reply_text(
        f"✅ *{_md(old_name)}* → *{_md(new_name)}*\n\n{msg}",
        parse_mode="Markdown",
        reply_markup=teams_action_keyboard(),
    )


async def cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.chat_data.pop("waiting_rename", None):
        await update.message.reply_text("❌ Перейменування скасовано.", reply_markup=main_menu_keyboard())
    else:
        await update.message.reply_text("Немає активних операцій.", reply_markup=main_menu_keyboard())
