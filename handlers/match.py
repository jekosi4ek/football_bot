import asyncio
import logging
import os
from telegram import Update
from telegram.ext import ContextTypes

from config import WHISTLE_SOUND_PATH
import database as db
from utils.keyboards import (
    main_menu_keyboard,
    match_duration_keyboard,
    timer_running_keyboard,
    timer_paused_keyboard,
)

logger = logging.getLogger(__name__)

# In-process timer state keyed by chat_id
_timers: dict[int, dict] = {}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fmt(seconds: int) -> str:
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def _progress_bar(remaining: int, total: int, width: int = 12) -> str:
    done = int(width * (total - remaining) / total)
    return "█" * done + "░" * (width - done)


def _timer_text(remaining: int, total: int, paused: bool = False) -> str:
    bar = _progress_bar(remaining, total)
    pct = int((total - remaining) / total * 100)
    status = "⏸ ПАУЗА" if paused else "▶️ Відлік"
    return (
        f"⏱ *Таймер тайму*  •  {status}\n\n"
        f"⏰ Залишилось: `{_fmt(remaining)}`\n"
        f"`[{bar}]` {pct}%\n\n"
        f"_Тривалість тайму: {total // 60} хв_"
    )


# ── Background timer task ─────────────────────────────────────────────────────

async def _run_timer(context, chat_id: int, message_id: int, total: int):
    state = _timers[chat_id]
    last_edit = total  # track last remaining value we edited the message with

    while state["remaining"] > 0 and not state["stopped"]:
        if state["paused"]:
            await asyncio.sleep(0.5)
            continue

        await asyncio.sleep(1)
        state["remaining"] -= 1
        rem = state["remaining"]

        # Edit message every 5 s, or every second in last 10 s
        tick = 5 if rem > 10 else 1
        if (last_edit - rem) >= tick or rem == 0:
            last_edit = rem
            try:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=_timer_text(rem, total),
                    parse_mode="Markdown",
                    reply_markup=timer_running_keyboard(),
                )
            except Exception as e:
                logger.debug("Timer edit skipped: %s", e)

    if not state["stopped"]:
        await _on_time_up(context, chat_id, message_id, total)


async def _on_time_up(context, chat_id: int, message_id: int, total: int):
    state = _timers.get(chat_id, {})
    state["stopped"] = True

    try:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text="⏱ *Таймер тайму*\n\n✅ *ТАЙМ ЗАКІНЧЕНО!*",
            parse_mode="Markdown",
        )
    except Exception:
        pass

    await context.bot.send_message(
        chat_id=chat_id,
        text=(
            "🔔🔔🔔 *КІНЕЦЬ ТАЙМУ!* 🔔🔔🔔\n\n"
            "📣 Свисток судді!\n"
            "_Зупиніться, зробіть заміни та відпочиньте._"
        ),
        parse_mode="Markdown",
    )

    # Send audio whistle if the file exists
    if os.path.exists(WHISTLE_SOUND_PATH):
        try:
            with open(WHISTLE_SOUND_PATH, "rb") as audio:
                await context.bot.send_audio(
                    chat_id=chat_id,
                    audio=audio,
                    title="Свисток судді",
                    performer="⚽ Football Timer",
                )
        except Exception as e:
            logger.warning("Could not send whistle audio: %s", e)
    else:
        # Fallback: text alarm
        await context.bot.send_message(
            chat_id=chat_id,
            text="📯 *ФІНАЛЬНИЙ СВИСТОК!* ⚽🏆",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard(),
        )


# ── /start_match ──────────────────────────────────────────────────────────────

async def start_match_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    state = _timers.get(chat_id, {})

    if state and not state.get("stopped", True):
        await update.message.reply_text(
            "⚠️ Таймер вже запущений!\n"
            "Зупиніть поточний матч командою /stop\\_match",
            parse_mode="Markdown",
        )
        return

    # If duration passed as argument: /start_match 10
    if context.args:
        try:
            minutes = int(context.args[0])
            if 1 <= minutes <= 60:
                await _launch_timer(update, context, chat_id, minutes * 60)
                return
        except ValueError:
            pass

    await update.message.reply_text(
        "⏱ *Виберіть тривалість тайму:*",
        parse_mode="Markdown",
        reply_markup=match_duration_keyboard(),
    )


async def _launch_timer(update_or_query, context, chat_id: int, total: int):
    """Create the timer state and start the background task.

    update_or_query can be:
      - telegram.Update (command path)  → reply via update_or_query.message
      - telegram.CallbackQuery (button) → edit via update_or_query.edit_message_text
    """
    db.save_match(total, chat_id)

    from telegram import Update as TGUpdate
    if isinstance(update_or_query, TGUpdate):
        # Called from a command handler
        sent = await update_or_query.message.reply_text(
            _timer_text(total, total),
            parse_mode="Markdown",
            reply_markup=timer_running_keyboard(),
        )
        message_id = sent.message_id
    else:
        # Called from a CallbackQuery — edit the existing message in-place
        await update_or_query.edit_message_text(
            _timer_text(total, total),
            parse_mode="Markdown",
            reply_markup=timer_running_keyboard(),
        )
        message_id = update_or_query.message.message_id

    _timers[chat_id] = {
        "remaining": total,
        "total": total,
        "paused": False,
        "stopped": False,
        "task": None,
    }

    task = asyncio.create_task(
        _run_timer(context, chat_id, message_id, total)
    )
    _timers[chat_id]["task"] = task


# ── /pause_timer ──────────────────────────────────────────────────────────────

async def pause_timer_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    state = _timers.get(chat_id)

    if not state or state.get("stopped", True):
        await update.message.reply_text("❌ Немає активного таймера.")
        return
    if state["paused"]:
        await update.message.reply_text("⏸ Таймер вже на паузі.")
        return

    state["paused"] = True
    await update.message.reply_text(
        f"⏸ *Пауза*\n⏰ Залишилось: `{_fmt(state['remaining'])}`",
        parse_mode="Markdown",
        reply_markup=timer_paused_keyboard(),
    )


# ── /resume_timer ─────────────────────────────────────────────────────────────

async def resume_timer_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    state = _timers.get(chat_id)

    if not state or state.get("stopped", True):
        await update.message.reply_text("❌ Немає активного таймера.")
        return
    if not state["paused"]:
        await update.message.reply_text("▶️ Таймер вже запущений.")
        return

    state["paused"] = False
    await update.message.reply_text(
        f"▶️ *Продовжено!*\n⏰ Залишилось: `{_fmt(state['remaining'])}`",
        parse_mode="Markdown",
        reply_markup=timer_running_keyboard(),
    )


# ── /stop_match ───────────────────────────────────────────────────────────────

async def stop_match_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    state = _timers.get(chat_id)

    if not state or state.get("stopped", True):
        await update.message.reply_text("❌ Немає активного таймера.")
        return

    state["stopped"] = True
    if state.get("task"):
        state["task"].cancel()

    await update.message.reply_text(
        "⏹ Матч зупинено вручну.",
        reply_markup=main_menu_keyboard(),
    )


# ── Exported helper for callback handler ─────────────────────────────────────

def get_timer_state(chat_id: int) -> dict | None:
    return _timers.get(chat_id)


async def launch_timer_from_callback(query, context, chat_id: int, total: int):
    await _launch_timer(query, context, chat_id, total)


def pause_from_callback(chat_id: int) -> bool:
    state = _timers.get(chat_id)
    if state and not state.get("stopped", True) and not state["paused"]:
        state["paused"] = True
        return True
    return False


def resume_from_callback(chat_id: int) -> bool:
    state = _timers.get(chat_id)
    if state and not state.get("stopped", True) and state["paused"]:
        state["paused"] = False
        return True
    return False


def stop_from_callback(chat_id: int) -> bool:
    state = _timers.get(chat_id)
    if state and not state.get("stopped", True):
        state["stopped"] = True
        if state.get("task"):
            state["task"].cancel()
        return True
    return False
