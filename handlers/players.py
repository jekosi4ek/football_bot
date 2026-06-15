import logging
from telegram import Update
from telegram.ext import ContextTypes

import database as db
from utils.keyboards import (
    main_menu_keyboard,
    players_remove_keyboard,
    players_strength_keyboard,
    strength_keyboard,
)

logger = logging.getLogger(__name__)

STRENGTH_LABEL = {1: "⭐ Слабкий", 2: "⭐⭐ Середній", 3: "⭐⭐⭐ Сильний"}


# ── /start ────────────────────────────────────────────────────────────────────

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚽ *Вітаємо у Football Manager Bot!*\n\n"
        "Цей бот допоможе вам:\n"
        "• Керувати списком гравців\n"
        "• Автоматично ділити на збалансовані команди\n"
        "• Запускати таймер тайму з сигналом\n\n"
        "Оберіть дію нижче або використовуйте команди:",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(),
    )


# ── /add_player ───────────────────────────────────────────────────────────────

async def add_player_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    chat_id = update.effective_chat.id

    if not args:
        await update.message.reply_text(
            "✏️ Введіть ім'я гравця:\n"
            "`/add_player Іванець`\n\n"
            "Або надішліть _голосове повідомлення_ з іменем гравця 🎙",
            parse_mode="Markdown",
        )
        return

    name = " ".join(args).strip()
    if len(name) < 2:
        await update.message.reply_text("❌ Ім'я занадто коротке. Мінімум 2 символи.")
        return
    if len(name) > 50:
        await update.message.reply_text("❌ Ім'я занадто довге. Максимум 50 символів.")
        return

    if db.player_exists(name, chat_id):
        await update.message.reply_text(f"⚠️ Гравець *{name}* вже є у списку.", parse_mode="Markdown")
        return

    player_id = db.add_player(name, chat_id)
    await update.message.reply_text(
        f"✅ Гравець *{name}* доданий (ID: {player_id})\n"
        f"Рівень сили: ⭐⭐ Середній\n\n"
        f"Щоб змінити силу: /set\\_strength",
        parse_mode="Markdown",
        reply_markup=strength_keyboard(player_id),
    )


# ── /list_players ─────────────────────────────────────────────────────────────

async def list_players_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    players = db.get_players(chat_id)

    if not players:
        await update.message.reply_text(
            "📋 Список гравців порожній.\n\nДодайте гравців командою /add\\_player",
            parse_mode="Markdown",
        )
        return

    lines = [f"📋 *Гравці ({len(players)}):*\n"]
    for p in players:
        stars = "⭐" * p["strength"]
        lines.append(f"• {p['name']} — {stars}")
    lines.append(f"\n_Загальна сила: {sum(p['strength'] for p in players)}_")

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(),
    )


# ── /remove_player ────────────────────────────────────────────────────────────

async def remove_player_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    args = context.args

    players = db.get_players(chat_id)
    if not players:
        await update.message.reply_text("📋 Список гравців порожній.")
        return

    # Direct removal by name: /remove_player Іванець
    if args:
        name = " ".join(args).strip()
        target = next((p for p in players if p["name"].lower() == name.lower()), None)
        if not target:
            await update.message.reply_text(f"❌ Гравця *{name}* не знайдено.", parse_mode="Markdown")
            return
        db.remove_player(target["id"], chat_id)
        await update.message.reply_text(
            f"🗑 Гравець *{target['name']}* видалений.",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard(),
        )
        return

    # Interactive: show inline buttons
    await update.message.reply_text(
        "❌ *Оберіть гравця для видалення:*",
        parse_mode="Markdown",
        reply_markup=players_remove_keyboard(players),
    )


# ── /set_strength ─────────────────────────────────────────────────────────────

async def set_strength_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    args = context.args

    players = db.get_players(chat_id)
    if not players:
        await update.message.reply_text("📋 Список гравців порожній. Спочатку додайте гравців.")
        return

    # Direct: /set_strength Іванець 3
    if len(args) >= 2:
        name = " ".join(args[:-1]).strip()
        try:
            strength = int(args[-1])
        except ValueError:
            await update.message.reply_text("❌ Рівень сили має бути числом 1, 2 або 3.")
            return

        if strength not in (1, 2, 3):
            await update.message.reply_text("❌ Рівень сили: 1 (слабкий), 2 (середній), 3 (сильний).")
            return

        target = next((p for p in players if p["name"].lower() == name.lower()), None)
        if not target:
            await update.message.reply_text(f"❌ Гравця *{name}* не знайдено.", parse_mode="Markdown")
            return

        db.update_player_strength(target["id"], strength, chat_id)
        await update.message.reply_text(
            f"✅ Гравець *{target['name']}* → {STRENGTH_LABEL[strength]}",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard(),
        )
        return

    # Interactive: choose player
    await update.message.reply_text(
        "⭐ *Оберіть гравця для зміни сили:*",
        parse_mode="Markdown",
        reply_markup=players_strength_keyboard(players),
    )
