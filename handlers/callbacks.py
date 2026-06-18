"""Central dispatcher for all InlineKeyboard CallbackQuery events."""

import logging
from telegram import Update
from telegram.ext import ContextTypes

import database as db
from services.team_divider import divide_players, format_teams_message
from handlers.session import (
    get_session_players, handle_sess_toggle, handle_sess_confirm,
    _session_keyboard, _sessions,
)
from handlers.match import (
    _fmt, get_timer_state, launch_timer_from_callback,
    pause_from_callback, resume_from_callback, stop_from_callback,
)
from handlers.tournament import (
    handle_tourn_schedule, handle_tourn_standings, handle_tourn_match,
    handle_score_t1, handle_score_save, handle_tourn_reset, handle_tourn_page,
    _create_and_show_tournament,
)
from utils.keyboards import (
    main_menu_keyboard, players_remove_keyboard, players_strength_keyboard,
    strength_keyboard, timer_running_keyboard, timer_paused_keyboard,
    teams_count_keyboard, after_divide_keyboard,
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

    # ── Player list ───────────────────────────────────────────────────────────
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
            "\n".join(lines), parse_mode="Markdown", reply_markup=main_menu_keyboard()
        )

    elif data == "menu_add_player":
        await query.edit_message_text(
            "✏️ *Додати гравця:*\n\n"
            "Команда: `/add_player Іванець`\n"
            "Або 🎙 надішліть голосове повідомлення.",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard(),
        )

    elif data == "menu_remove_player":
        players = db.get_players(chat_id)
        if not players:
            await query.edit_message_text("📋 Список гравців порожній.", reply_markup=main_menu_keyboard())
            return
        await query.edit_message_text(
            "❌ *Оберіть гравця для видалення:*",
            parse_mode="Markdown",
            reply_markup=players_remove_keyboard(players),
        )

    elif data == "menu_set_strength":
        players = db.get_players(chat_id)
        if not players:
            await query.edit_message_text("📋 Список гравців порожній.", reply_markup=main_menu_keyboard())
            return
        await query.edit_message_text(
            "⭐ *Оберіть гравця для зміни рівня сили:*",
            parse_mode="Markdown",
            reply_markup=players_strength_keyboard(players),
        )

    # ── Teams ─────────────────────────────────────────────────────────────────
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
        try:
            msg = format_teams_message(teams, players)
            await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=main_menu_keyboard())
        except Exception as e:
            logger.error("format_teams_message error: %s", e)
            await query.edit_message_text(
                "⚠️ Помилка відображення. Спробуйте команду /show\\_teams",
                parse_mode="Markdown",
                reply_markup=main_menu_keyboard(),
            )

    elif data == "menu_auto_divide":
        all_players = db.get_players(chat_id)
        players = get_session_players(chat_id, all_players)
        if len(players) < 2:
            await query.edit_message_text(
                "⚠️ Потрібно мінімум *2 гравці*.",
                parse_mode="Markdown",
                reply_markup=main_menu_keyboard(),
            )
            return
        note = f"_Сесія: {len(players)} з {len(all_players)} гравців_\n\n" if len(players) != len(all_players) else ""
        await query.edit_message_text(
            f"{note}⚽ Гравців: *{len(players)}*\n\nНа скільки команд ділити?",
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

    # ── Game session ──────────────────────────────────────────────────────────
    elif data == "menu_game_session":
        players = db.get_players(chat_id)
        if not players:
            await query.edit_message_text(
                "📋 Список гравців порожній. Спочатку додайте гравців.",
                reply_markup=main_menu_keyboard(),
            )
            return
        if chat_id not in _sessions:
            _sessions[chat_id] = {p["id"] for p in players}
        active_ids = _sessions[chat_id]
        await query.edit_message_text(
            f"🎮 *Хто грає сьогодні?*\n\n"
            f"Натисніть на гравця щоб відмітити.\n"
            f"Активних: *{len(active_ids)}* з {len(players)}",
            parse_mode="Markdown",
            reply_markup=_session_keyboard(players, active_ids),
        )

    elif data.startswith("sess_toggle_"):
        player_id = int(data.split("_")[2])
        await handle_sess_toggle(query, chat_id, player_id)

    elif data == "sess_confirm":
        await handle_sess_confirm(query, chat_id)

    # ── Tournament ────────────────────────────────────────────────────────────
    elif data == "menu_tournament":
        teams = db.get_teams(chat_id)
        if len(teams) < 2:
            await query.edit_message_text(
                "⚠️ Потрібно мінімум *2 команди*.\nСпочатку: /auto\\_divide",
                parse_mode="Markdown",
                reply_markup=main_menu_keyboard(),
            )
            return
        await _create_and_show_tournament(query, chat_id, teams)

    elif data == "tourn_schedule":
        await handle_tourn_schedule(query, chat_id)

    elif data == "tourn_standings":
        await handle_tourn_standings(query, chat_id)

    elif data == "tourn_reset":
        await handle_tourn_reset(query, chat_id)

    elif data.startswith("tourn_page_"):
        page = int(data.split("_")[2])
        await handle_tourn_page(query, chat_id, page)

    elif data == "noop":
        pass  # page-counter button, do nothing

    elif data.startswith("tourn_match_"):
        match_id = int(data.split("_")[2])
        await handle_tourn_match(query, chat_id, match_id)

    elif data.startswith("score_t1_"):
        parts = data.split("_")
        match_id, t1_score = int(parts[2]), int(parts[3])
        await handle_score_t1(query, chat_id, match_id, t1_score)

    elif data.startswith("score_save_"):
        parts = data.split("_")
        match_id, t1_score, t2_score = int(parts[2]), int(parts[3]), int(parts[4])
        await handle_score_save(query, chat_id, match_id, t1_score, t2_score)

    # ── Remove player ─────────────────────────────────────────────────────────
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
            await query.edit_message_text("🗑 Усіх гравців видалено.", reply_markup=main_menu_keyboard())

    # ── Strength ──────────────────────────────────────────────────────────────
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

    elif data.startswith("strength_"):
        parts = data.split("_")
        player_id, strength = int(parts[1]), int(parts[2])
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

    # ── Team count ────────────────────────────────────────────────────────────
    elif data.startswith("teams_"):
        num_teams = int(data.split("_")[1])
        all_players = db.get_players(chat_id)
        players = get_session_players(chat_id, all_players)
        if len(players) < 2:
            await query.edit_message_text("⚠️ Недостатньо гравців.", reply_markup=main_menu_keyboard())
            return
        teams = divide_players(players, num_teams)
        db.save_teams([{"name": t["name"], "player_ids": t["player_ids"]} for t in teams], chat_id)
        msg = format_teams_message(teams, players)
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=after_divide_keyboard())

    # ── Timer ─────────────────────────────────────────────────────────────────
    elif data.startswith("duration_"):
        minutes = int(data.split("_")[1])
        total = minutes * 60
        state = get_timer_state(chat_id)
        if state and not state.get("stopped", True):
            await query.answer("Таймер вже запущений!", show_alert=True)
            return
        await launch_timer_from_callback(query, context, chat_id, total)

    elif data == "timer_pause":
        if pause_from_callback(chat_id):
            await query.answer("⏸ Пауза")
            try:
                await query.edit_message_reply_markup(reply_markup=timer_paused_keyboard())
            except Exception:
                pass
        else:
            await query.answer("Неможливо поставити на паузу.", show_alert=True)

    elif data == "timer_resume":
        if resume_from_callback(chat_id):
            await query.answer("▶️ Продовжено")
            try:
                await query.edit_message_reply_markup(reply_markup=timer_running_keyboard())
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
