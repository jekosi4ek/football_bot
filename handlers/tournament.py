"""
Tournament management: create round-robin, show schedule/standings, enter scores.
"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

import database as db
from services.tournament import (
    generate_round_robin,
    format_schedule,
    format_standings,
    parse_score,
    parse_match_and_score,
)
from utils.keyboards import main_menu_keyboard

logger = logging.getLogger(__name__)


# ── Keyboard builders ─────────────────────────────────────────────────────────

def _tournament_keyboard(matches: list[dict]) -> InlineKeyboardMarkup:
    rows = []
    for m in matches:
        if m.get("played") and m["team1_score"] is not None:
            label = f"✅ {m['match_order']}. {m['team1_name']} {m['team1_score']}:{m['team2_score']} {m['team2_name']}"
        else:
            label = f"⚽ {m['match_order']}. {m['team1_name']} vs {m['team2_name']}"
        rows.append([InlineKeyboardButton(label, callback_data=f"tourn_match_{m['id']}")])

    rows.append([
        InlineKeyboardButton("🏆 Таблиця", callback_data="tourn_standings"),
        InlineKeyboardButton("🔄 Новий турнір", callback_data="tourn_reset"),
    ])
    rows.append([InlineKeyboardButton("🔙 Головне меню", callback_data="back_main")])
    return InlineKeyboardMarkup(rows)


def _score_keyboard(match_id: int) -> InlineKeyboardMarkup:
    """Quick-pick score keyboard 0-6 for each team."""
    rows = []
    # Row for team1 score (left number)
    rows.append([InlineKeyboardButton(f"{i}-?", callback_data=f"score_t1_{match_id}_{i}") for i in range(7)])
    rows.append([InlineKeyboardButton("🔙 Назад", callback_data="tourn_schedule")])
    return InlineKeyboardMarkup(rows)


def _score_t2_keyboard(match_id: int, t1_score: int) -> InlineKeyboardMarkup:
    rows = []
    rows.append([InlineKeyboardButton(f"{t1_score}-{i}", callback_data=f"score_save_{match_id}_{t1_score}_{i}") for i in range(7)])
    rows.append([InlineKeyboardButton("🔙 Назад", callback_data="tourn_schedule")])
    return InlineKeyboardMarkup(rows)


# ── /tournament command ───────────────────────────────────────────────────────

async def tournament_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    teams = db.get_teams(chat_id)

    if len(teams) < 2:
        await update.message.reply_text(
            "⚠️ Потрібно мінімум *2 команди* для турніру.\n"
            "Спочатку розділіть гравців: /auto\\_divide",
            parse_mode="Markdown",
        )
        return

    await _create_and_show_tournament(update.message, chat_id, teams)


async def _create_and_show_tournament(msg_or_query, chat_id: int, teams: list[dict]):
    team_names = [t["name"] for t in teams]
    matches = generate_round_robin(team_names)
    db.save_tournament(matches, chat_id)
    saved = db.get_tournament(chat_id)

    text = format_schedule(saved)
    kb = _tournament_keyboard(saved)

    if hasattr(msg_or_query, "reply_text"):
        await msg_or_query.reply_text(text, parse_mode="Markdown", reply_markup=kb)
    else:
        await msg_or_query.edit_message_text(text, parse_mode="Markdown", reply_markup=kb)


# ── /score command ────────────────────────────────────────────────────────────

async def score_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /score <match_num> <goals1> <goals2>
    Example: /score 2 3 1
    """
    chat_id = update.effective_chat.id
    args = context.args

    if len(args) != 3:
        await update.message.reply_text(
            "📝 Формат: `/score <номер_матчу> <голи_А> <голи_Б>`\n"
            "Приклад: `/score 2 3 1`\n\n"
            "Або перегляньте розклад: /show\\_tournament",
            parse_mode="Markdown",
        )
        return

    try:
        match_num = int(args[0])
        s1, s2 = int(args[1]), int(args[2])
    except ValueError:
        await update.message.reply_text("❌ Введіть цілі числа. Приклад: `/score 1 3 1`",
                                        parse_mode="Markdown")
        return

    if not (0 <= s1 <= 20 and 0 <= s2 <= 20):
        await update.message.reply_text("❌ Рахунок від 0 до 20.")
        return

    matches = db.get_tournament(chat_id)
    target = next((m for m in matches if m["match_order"] == match_num), None)
    if not target:
        await update.message.reply_text(f"❌ Матч №{match_num} не знайдено. Перевірте /show\\_tournament",
                                        parse_mode="Markdown")
        return

    db.update_match_score(target["id"], s1, s2, chat_id)
    matches = db.get_tournament(chat_id)
    teams = db.get_teams(chat_id)
    team_names = [t["name"] for t in teams]

    schedule_text = format_schedule(matches)
    standings_text = format_standings(team_names, matches)
    text = f"{schedule_text}\n\n{standings_text}"

    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=_tournament_keyboard(matches),
    )


# ── /show_tournament command ──────────────────────────────────────────────────

async def show_tournament_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    matches = db.get_tournament(chat_id)

    if not matches:
        await update.message.reply_text(
            "🏆 Турнір не розпочато.\n\nСтворіть командою /tournament",
        )
        return

    teams = db.get_teams(chat_id)
    team_names = [t["name"] for t in teams]
    text = format_schedule(matches) + "\n\n" + format_standings(team_names, matches)
    await update.message.reply_text(
        text, parse_mode="Markdown", reply_markup=_tournament_keyboard(matches)
    )


# ── Voice score handler ───────────────────────────────────────────────────────

async def handle_score_voice(update: Update, context: ContextTypes.DEFAULT_TYPE, transcribed: str):
    """Called from voice.py when score voice is detected."""
    chat_id = update.effective_chat.id
    result = parse_match_and_score(transcribed)
    if not result:
        return False

    match_num, s1, s2 = result
    matches = db.get_tournament(chat_id)
    target = next((m for m in matches if m["match_order"] == match_num), None)
    if not target:
        return False

    db.update_match_score(target["id"], s1, s2, chat_id)
    matches = db.get_tournament(chat_id)
    teams = db.get_teams(chat_id)
    team_names = [t["name"] for t in teams]
    text = format_schedule(matches) + "\n\n" + format_standings(team_names, matches)
    await update.message.reply_text(
        f"⚽ Рахунок збережено: Матч {match_num} — {s1}:{s2}\n\n{text}",
        parse_mode="Markdown",
        reply_markup=_tournament_keyboard(matches),
    )
    return True


# ── Callback handlers (called from callbacks.py) ──────────────────────────────

async def handle_tourn_schedule(query, chat_id: int):
    matches = db.get_tournament(chat_id)
    if not matches:
        await query.edit_message_text("🏆 Турнір не розпочато.", reply_markup=main_menu_keyboard())
        return
    await query.edit_message_text(
        format_schedule(matches),
        parse_mode="Markdown",
        reply_markup=_tournament_keyboard(matches),
    )


async def handle_tourn_standings(query, chat_id: int):
    matches = db.get_tournament(chat_id)
    teams = db.get_teams(chat_id)
    if not matches or not teams:
        await query.answer("Немає даних.", show_alert=True)
        return
    team_names = [t["name"] for t in teams]
    text = format_schedule(matches) + "\n\n" + format_standings(team_names, matches)
    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=_tournament_keyboard(matches),
    )


async def handle_tourn_match(query, chat_id: int, match_id: int):
    matches = db.get_tournament(chat_id)
    m = next((x for x in matches if x["id"] == match_id), None)
    if not m:
        await query.answer("Матч не знайдено.", show_alert=True)
        return
    await query.edit_message_text(
        f"⚽ *Матч {m['match_order']}:* {m['team1_name']} vs {m['team2_name']}\n\n"
        f"Оберіть голи *{m['team1_name']}*:",
        parse_mode="Markdown",
        reply_markup=_score_keyboard(match_id),
    )


async def handle_score_t1(query, chat_id: int, match_id: int, t1_score: int):
    matches = db.get_tournament(chat_id)
    m = next((x for x in matches if x["id"] == match_id), None)
    if not m:
        await query.answer("Матч не знайдено.", show_alert=True)
        return
    await query.edit_message_text(
        f"⚽ *Матч {m['match_order']}:* {m['team1_name']} *{t1_score}* : ? {m['team2_name']}\n\n"
        f"Оберіть голи *{m['team2_name']}*:",
        parse_mode="Markdown",
        reply_markup=_score_t2_keyboard(match_id, t1_score),
    )


async def handle_score_save(query, chat_id: int, match_id: int, t1_score: int, t2_score: int):
    matches = db.get_tournament(chat_id)
    m = next((x for x in matches if x["id"] == match_id), None)
    if not m:
        await query.answer("Матч не знайдено.", show_alert=True)
        return

    db.update_match_score(match_id, t1_score, t2_score, chat_id)
    await query.answer(f"✅ {t1_score}:{t2_score} збережено")

    matches = db.get_tournament(chat_id)
    teams = db.get_teams(chat_id)
    team_names = [t["name"] for t in teams]
    text = format_schedule(matches) + "\n\n" + format_standings(team_names, matches)
    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=_tournament_keyboard(matches),
    )


async def handle_tourn_reset(query, chat_id: int):
    teams = db.get_teams(chat_id)
    if len(teams) < 2:
        await query.answer("Спочатку сформуйте команди.", show_alert=True)
        return
    await _create_and_show_tournament(query, chat_id, teams)
    await query.answer("🔄 Турнір перезапущено")
