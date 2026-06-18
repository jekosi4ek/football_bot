from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ Додати гравця",   callback_data="menu_add_player"),
            InlineKeyboardButton("📋 Список гравців",  callback_data="menu_list_players"),
        ],
        [
            InlineKeyboardButton("✏️ Сила гравця",    callback_data="menu_set_strength"),
            InlineKeyboardButton("❌ Видалити гравця", callback_data="menu_remove_player"),
        ],
        [
            InlineKeyboardButton("🎮 Хто грає сьогодні", callback_data="menu_game_session"),
        ],
        [
            InlineKeyboardButton("⚽ Авторозподіл",   callback_data="menu_auto_divide"),
            InlineKeyboardButton("👥 Команди",         callback_data="menu_show_teams"),
        ],
        [
            InlineKeyboardButton("🏆 Турнір",          callback_data="menu_tournament"),
            InlineKeyboardButton("⏱ Таймер",           callback_data="menu_start_match"),
        ],
    ])


def strength_keyboard(player_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⭐ Слабкий (1)",     callback_data=f"strength_{player_id}_1"),
            InlineKeyboardButton("⭐⭐ Середній (2)",  callback_data=f"strength_{player_id}_2"),
            InlineKeyboardButton("⭐⭐⭐ Сильний (3)", callback_data=f"strength_{player_id}_3"),
        ],
        [InlineKeyboardButton("🔙 Назад", callback_data="menu_set_strength")],
    ])


def players_remove_keyboard(players: list[dict]) -> InlineKeyboardMarkup:
    rows = []
    for p in players:
        stars = "⭐" * p["strength"]
        rows.append([InlineKeyboardButton(
            f"❌ {p['name']} {stars}",
            callback_data=f"remove_{p['id']}",
        )])
    rows.append([InlineKeyboardButton("🔙 Головне меню", callback_data="back_main")])
    return InlineKeyboardMarkup(rows)


def players_strength_keyboard(players: list[dict]) -> InlineKeyboardMarkup:
    rows = []
    for p in players:
        stars = "⭐" * p["strength"]
        rows.append([InlineKeyboardButton(
            f"{p['name']} {stars}",
            callback_data=f"edit_strength_{p['id']}",
        )])
    rows.append([InlineKeyboardButton("🔙 Головне меню", callback_data="back_main")])
    return InlineKeyboardMarkup(rows)


def match_duration_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("5 хв",  callback_data="duration_5"),
            InlineKeyboardButton("7 хв",  callback_data="duration_7"),
            InlineKeyboardButton("10 хв", callback_data="duration_10"),
        ],
        [
            InlineKeyboardButton("12 хв", callback_data="duration_12"),
            InlineKeyboardButton("15 хв", callback_data="duration_15"),
            InlineKeyboardButton("20 хв", callback_data="duration_20"),
        ],
        [InlineKeyboardButton("🔙 Скасувати", callback_data="back_main")],
    ])


def timer_running_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("⏸ Пауза",    callback_data="timer_pause"),
        InlineKeyboardButton("⏹ Зупинити", callback_data="timer_stop"),
    ]])


def timer_paused_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("▶️ Продовжити", callback_data="timer_resume"),
        InlineKeyboardButton("⏹ Зупинити",   callback_data="timer_stop"),
    ]])


def teams_count_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("2 команди", callback_data="teams_2"),
            InlineKeyboardButton("3 команди", callback_data="teams_3"),
            InlineKeyboardButton("4 команди", callback_data="teams_4"),
        ],
        [InlineKeyboardButton("🔙 Скасувати", callback_data="back_main")],
    ])


def after_divide_keyboard() -> InlineKeyboardMarkup:
    """Shown after auto-divide — rename, tournament, timer."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ Назви команд",     callback_data="rename_pick")],
        [InlineKeyboardButton("🏆 Створити турнір",  callback_data="menu_tournament")],
        [InlineKeyboardButton("⏱ Почати таймер",     callback_data="menu_start_match")],
        [InlineKeyboardButton("🔙 Головне меню",      callback_data="back_main")],
    ])


def teams_action_keyboard() -> InlineKeyboardMarkup:
    """Shown when viewing existing teams."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ Назви команд", callback_data="rename_pick")],
        [
            InlineKeyboardButton("🏆 Турнір",   callback_data="menu_tournament"),
            InlineKeyboardButton("⏱ Таймер",    callback_data="menu_start_match"),
        ],
        [InlineKeyboardButton("🔙 Головне меню", callback_data="back_main")],
    ])


def tournament_rounds_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("1 тур",  callback_data="tourn_rounds_1"),
            InlineKeyboardButton("2 тури", callback_data="tourn_rounds_2"),
            InlineKeyboardButton("3 тури", callback_data="tourn_rounds_3"),
        ],
        [InlineKeyboardButton("🔙 Скасувати", callback_data="back_main")],
    ])


def teams_rename_keyboard(teams: list[dict]) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(f"✏️ {t['name']}", callback_data=f"rename_{i}")]
            for i, t in enumerate(teams)]
    rows.append([InlineKeyboardButton("🔙 Назад", callback_data="menu_show_teams")])
    return InlineKeyboardMarkup(rows)
