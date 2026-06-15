"""
Central dispatcher for all InlineKeyboard CallbackQuery events.
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes

import database as db
from services.team_divider import divide_players, format_teams_message
from utils.keyboards import (
    main_menu_keyboard,
    players_remove_keyboard,
    players_strength_keyboard,
    strength_keyboard,
    timer_running_keyboard,
    timer_paused_keyboard,
)
from handlers.match import (
    _fmt,
    get_timer_state,
    launch_timer_from_callback,
    pause_from_callback,
    resume_from_callback,
    stop_from_callback,
)

logger = logging.getLogger(__name__)

STRENGTH_LABEL = {1: "⭐ Слабкий", 2: "⭐⭐ Середній", 3: "⭐⭐⭐ Сильний"}


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data: str = query.data
    chat_id = update.effective_chat.id

    # ── Navigation ────────────────────────────────────────────────────────────
    if data == "back_main":
        await query.edit_message_text(
            "⚽ *Football Manager* — головне меню",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard(),
        )

    # ── Menu shortcuts ────────────────────────────────────────────────────────
    elif data == "menu_list_players":
        players = db.get_players(chat_id)
        if not players:
            await query.edit_message_text(
                "📋 Список гравців порожній.\n\nДодайте: /add\\_player",
                parse_mode="Markdown",
                reply_markup=main_menu_keyboard(),
            )
            return
        lines = [f"📋 *Гравці ({len(players)}):*\n"]
        for p in players:
            lines.append(f"• {p['name']} — {'⭐' * p['strength']}")
        lines.append(f"\n_Загальна сила: {sum(p['strength'] for p in players)}_")
        await query.edit_message_text(
            "\n".join(lines),
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard(),
        )

    elif data == "menu_add_player":
        await query.edit_message_text(
            "✏️ *Додати гравця:*\n\n"
            "Надішліть команду:\n`/add_player Іванець`\n\n"
            "Або надішліть 🎙 _голосове повідомлення_ з іменем.",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard(),
        )

    elif data == "menu_remove_player":
        players = db.get_players(chat_id)
        if not players:
            await query.edit_message_text(
                "📋 Список гравців порожній.",
                reply_markup=main_menu_keyboard(),
            )
            return
        await query.edit_message_text(
            "❌ *Оберіть гравця для видалення:*",
            parse_mode="Markdown",
            reply_markup=players_remove_keyboard(players),
        )

    elif data == "menu_set_strength":
        players = db.get_players(chat_id)
        if not players:
            await query.edit_message_text(
                "📋 Список гравців порожній.",
                reply_markup=main_menu_keyboard(),
            )
            return
        await query.edit_message_text(
            "⭐ *Оберіть гравця для зміни рівня сили:*",
            parse_mode="Markdown",
            reply_markup=players_strength_keyboard(players),
        )

    elif data == "menu_show_teams":
        teams = db.get_teams(chat_id)
        players = db.get_players(chat_id)
        if not teams:
            await query.edit_message_text(
                "👥 Команди ще не сформовані.\n\nВикористайте /auto\\_divide",
                parse_mode="Markdown",
                reply_markup=main_menu_keyboard(),
            )
            return
        msg = format_teams_message(teams, players)
        await query.edit_message_text(
            msg, parse_mode="Markdown", reply_markup=main_menu_keyboard()
        )

    elif data == "menu_auto_divide":
        players = db.get_players(chat_id)
        if len(players) < 2:
            await query.edit_message_text(
                "⚠️ Потрібно мінімум *2 гравці*.",
                parse_mode="Markdown",
                reply_markup=main_menu_keyboard(),
            )
            return
        from utils.keyboards import teams_count_keyboard
        await query.edit_message_text(
            f"⚽ Гравців: *{len(players)}*\n\nНа скільки команд ділити?",
            parse_mode="Markdown",
            reply_markup=teams_count_keyboard(),
        )

    elif data == "menu_start_match":
        from utils.keyboards import match_duration_keyboard
        await query.edit_message_text(
            "⏱ *Виберіть тривалість тайму:*",
            parse_mode="Markdown",
            reply_markup=match_duration_keyboard(),
        )

    # ── Remove player: remove_<id> ────────────────────────────────────────────
    elif data.startswith("remove_"):
        player_id = int(data.split("_")[1])
        player = db.get_player(player_id, chat_id)
        if not player:
            await query.answer("Гравця не знайдено.", show_alert=True)
            return
        db.remove_player(player_id, chat_id)
        await query.answer(f"✅ {player['name']} видалений")
        players = db.get_players(chat_id)
        if players:
            await query.edit_message_text(
                "❌ *Оберіть гравця для видалення:*",
                parse_mode="Markdown",
                reply_markup=players_remove_keyboard(players),
            )
        else:
            await query.edit_message_text(
                "🗑 Усіх гравців видалено.",
                reply_markup=main_menu_keyboard(),
            )

    # ── Edit strength picker: edit_strength_<id> ──────────────────────────────
    elif data.startswith("edit_strength_"):
        player_id = int(data.split("_")[2])
        player = db.get_player(player_id, chat_id)
        if not player:
            await query.answer("Гравця не знайдено.", show_alert=True)
            return
        await query.edit_message_text(
            f"⭐ *{player['name']}* — оберіть рівень сили:",
            parse_mode="Markdown",
            reply_markup=strength_keyboard(player_id),
        )

    # ── Set strength: strength_<id>_<level> ───────────────────────────────────
    elif data.startswith("strength_"):
        parts = data.split("_")
        player_id = int(parts[1])
        strength = int(parts[2])
        player = db.get_player(player_id, chat_id)
        if not player:
            await query.answer("Гравця не знайдено.", show_alert=True)
            return
        db.update_player_strength(player_id, strength, chat_id)
        await query.answer(f"Збережено: {STRENGTH_LABEL[strength]}")
        await query.edit_message_text(
            f"✅ *{player['name']}* → {STRENGTH_LABEL[strength]}",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard(),
        )

    # ── Team count: teams_<n> ─────────────────────────────────────────────────
    elif data.startswith("teams_"):
        num_teams = int(data.split("_")[1])
        players = db.get_players(chat_id)
        if len(players) < 2:
            await query.edit_message_text(
                "⚠️ Недостатньо гравців.",
                reply_markup=main_menu_keyboard(),
            )
            return
        teams = divide_players(players, num_teams)
        db.save_teams(
            [{"name": t["name"], "player_ids": t["player_ids"]} for t in teams],
            chat_id,
        )
        msg = format_teams_message(teams, players)
        await query.edit_message_text(
            msg, parse_mode="Markdown", reply_markup=main_menu_keyboard()
        )

    # ── Match duration: duration_<minutes> ────────────────────────────────────
    elif data.startswith("duration_"):
        minutes = int(data.split("_")[1])
        total = minutes * 60
        state = get_timer_state(chat_id)
        if state and not state.get("stopped", True):
            await query.answer("Таймер вже запущений!", show_alert=True)
            return
        await launch_timer_from_callback(query, context, chat_id, total)

    # ── Timer controls ────────────────────────────────────────────────────────
    elif data == "timer_pause":
        if pause_from_callback(chat_id):
            state = get_timer_state(chat_id)
            await query.answer("⏸ Пауза")
            try:
                await query.edit_message_reply_markup(
                    reply_markup=timer_paused_keyboard()
                )
            except Exception:
                pass
        else:
            await query.answer("Неможливо поставити на паузу.", show_alert=True)

    elif data == "timer_resume":
        if resume_from_callback(chat_id):
            state = get_timer_state(chat_id)
            await query.answer("▶️ Продовжено")
            try:
                await query.edit_message_reply_markup(
                    reply_markup=timer_running_keyboard()
                )
            except Exception:
                pass
        else:
            await query.answer("Неможливо відновити.", show_alert=True)

    elif data == "timer_stop":
        if stop_from_callback(chat_id):
            await query.answer("⏹ Зупинено")
            await query.edit_message_text(
                "⏹ *Матч зупинено вручну.*",
                parse_mode="Markdown",
                reply_markup=main_menu_keyboard(),
            )
        else:
            await query.answer("Таймер вже зупинений.", show_alert=True)

    else:
        logger.warning("Unknown callback data: %s", data)
        await query.answer("Невідома дія.", show_alert=True)
