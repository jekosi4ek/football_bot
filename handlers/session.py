"""
Game session — tracks which players are active for TODAY's game.

State is kept in-memory (ephemeral). Survives between commands within one
bot process; resets on bot restart, which is the expected behaviour for a
live game-day workflow.
"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

import database as db

logger = logging.getLogger(__name__)

# chat_id → set of active player IDs for today
_sessions: dict[int, set[int]] = {}


# ── Public API (used by other handlers) ───────────────────────────────────────

def get_session_players(chat_id: int, all_players: list[dict]) -> list[dict]:
    """Return today's active players. Falls back to all players if no session started."""
    if chat_id not in _sessions:
        return all_players
    ids = _sessions[chat_id]
    return [p for p in all_players if p["id"] in ids]


def session_active(chat_id: int) -> bool:
    return chat_id in _sessions


def init_session(chat_id: int, player_ids: list[int]):
    _sessions[chat_id] = set(player_ids)


def toggle_player_session(chat_id: int, player_id: int) -> bool:
    """Toggle a player in/out. Returns True if now active, False if removed."""
    if chat_id not in _sessions:
        return False
    if player_id in _sessions[chat_id]:
        _sessions[chat_id].discard(player_id)
        return False
    _sessions[chat_id].add(player_id)
    return True


def add_to_session(chat_id: int, player_id: int):
    if chat_id not in _sessions:
        _sessions[chat_id] = set()
    _sessions[chat_id].add(player_id)


# ── Keyboard builder ──────────────────────────────────────────────────────────

def _session_keyboard(players: list[dict], active_ids: set[int]) -> InlineKeyboardMarkup:
    rows = []
    # Two players per row
    for i in range(0, len(players), 2):
        row = []
        for p in players[i:i + 2]:
            mark = "✅" if p["id"] in active_ids else "❌"
            stars = "⭐" * p["strength"]
            row.append(InlineKeyboardButton(
                f"{mark} {p['name']} {stars}",
                callback_data=f"sess_toggle_{p['id']}",
            ))
        rows.append(row)

    active_count = len(active_ids)
    rows.append([InlineKeyboardButton(
        f"✅ Підтвердити ({active_count} гравців)",
        callback_data="sess_confirm",
    )])
    rows.append([InlineKeyboardButton("🔙 Головне меню", callback_data="back_main")])
    return InlineKeyboardMarkup(rows)


# ── /game command ─────────────────────────────────────────────────────────────

async def game_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    players = db.get_players(chat_id)

    if not players:
        await update.message.reply_text(
            "📋 Список гравців порожній. Спочатку додайте гравців: /add\\_player",
            parse_mode="Markdown",
        )
        return

    # Default: all players are active
    if chat_id not in _sessions:
        _sessions[chat_id] = {p["id"] for p in players}

    active_ids = _sessions[chat_id]
    await update.message.reply_text(
        f"🎮 *Хто грає сьогодні?*\n\n"
        f"Натисніть на гравця щоб відмітити присутність/відсутність.\n"
        f"Активних: *{len(active_ids)}* з {len(players)}",
        parse_mode="Markdown",
        reply_markup=_session_keyboard(players, active_ids),
    )


# ── Callback handlers (called from callbacks.py) ──────────────────────────────

async def handle_sess_toggle(query, chat_id: int, player_id: int):
    players = db.get_players(chat_id)
    now_active = toggle_player_session(chat_id, player_id)
    player = next((p for p in players if p["id"] == player_id), None)
    name = player["name"] if player else str(player_id)
    await query.answer(f"{'✅ Додано' if now_active else '❌ Прибрано'}: {name}")

    active_ids = _sessions.get(chat_id, set())
    await query.edit_message_text(
        f"🎮 *Хто грає сьогодні?*\n\n"
        f"Натисніть на гравця щоб відмітити присутність/відсутність.\n"
        f"Активних: *{len(active_ids)}* з {len(players)}",
        parse_mode="Markdown",
        reply_markup=_session_keyboard(players, active_ids),
    )


async def handle_sess_confirm(query, chat_id: int):
    from utils.keyboards import main_menu_keyboard
    players = db.get_players(chat_id)
    active_ids = _sessions.get(chat_id, {p["id"] for p in players})
    active = [p for p in players if p["id"] in active_ids]

    if not active:
        await query.answer("⚠️ Додайте хоча б одного гравця!", show_alert=True)
        return

    lines = [f"✅ *Сесію підтверджено!* Грають {len(active)} гравців:\n"]
    for p in active:
        lines.append(f"• {p['name']} {'⭐' * p['strength']}")
    lines.append("\nТепер використайте /auto\\_divide для розподілу на команди.")

    await query.edit_message_text(
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(),
    )
