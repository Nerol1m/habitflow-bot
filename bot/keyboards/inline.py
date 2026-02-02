from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# БЛОК SETTINGS
# Динамическая клавиатура настроек.
def settings_kb(user, time_value=None):
    rows = [
        [InlineKeyboardButton(text="🕐 Изменить часовой пояс", callback_data="change_timezone")],
        [InlineKeyboardButton(
            text=f"{'🔕 Выкл' if user.reminders_enabled else '🔔 Вкл'} напоминания",
            callback_data="toggle_reminders"
        )]
    ]

    # Динамическая кнопка (если напоминания включены)
    if user.reminders_enabled:
        display_time = time_value if time_value is not None else user.reminder_time

        rows.append([
            InlineKeyboardButton(
                text=f"⏰ Время: {display_time}",
                callback_data="change_reminder_time"
            )
        ])

    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")])

    return InlineKeyboardMarkup(inline_keyboard=rows)

# Клавиатура выбора часового пояса
def timezone_selection_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Москва (UTC+3)", callback_data="tz_UTC+3")],
        [InlineKeyboardButton(text="Калининград (UTC+2)", callback_data="tz_UTC+2")],
        [InlineKeyboardButton(text="Астана (UTC+5)", callback_data="tz_UTC+5")],
        [InlineKeyboardButton(text="Другой...", callback_data="tz_custom")]
    ])

# Клавиатура выбора времени напоминаний
def time_selection_kb():
    times = ["06:00", "07:00", "08:00", "09:00", "10:00", "12:00", "18:00", "21:00", "23:00"]

    keyboard_buttons = []
    row = []

    for i, time in enumerate(times):
        row.append(InlineKeyboardButton(text=time, callback_data=f"remtime_{time}"))
        if (i + 1) % 3 == 0:  # по 3 кнопки в строке
            keyboard_buttons.append(row)
            row = []

    if row:
        keyboard_buttons.append(row)

    keyboard_buttons.append([
        InlineKeyboardButton(text="✏️ Другое время...", callback_data="remtime_custom")
    ])

    return InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)



# БЛОК HABITS
# Клавиатура со списком привычек.
def habits_list_kb(habits_with_streaks):
    """
        Клавиатура со списком привычек.

        :param habits_with_streaks: Список кортежей (habit, streak_text)
        Пример: [(habit1, "🔥5"), (habit2, ""), ...]
    """
    keyboard = []

    for habit, streak_text in habits_with_streaks:
        button_text = f"{habit.name}{streak_text}"
        keyboard.append([
            InlineKeyboardButton(
                text=button_text,
                callback_data=f"habit_{habit.id}"
            )
        ])

    # Кнопка добавления новой привычки
    keyboard.append([
        InlineKeyboardButton(
            text="➕ Новая привычка",
            callback_data="new_habit"
        )
    ])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# Клавиатура меню привычки.
def habit_menu_kb(habit_id, is_today_logged):
    """
    Клавиатура меню привычки.

    :param habit_id: ID привычки
    :param is_today_logged: True - если привычка отмечена сегодня
    """
    keyboard = []

    # Кнопка отметки/отмены
    if is_today_logged:
        keyboard.append([
            InlineKeyboardButton(
                text="❌ Отменить сегодняшнюю отметку",
                callback_data=f"unlog_{habit_id}"
            )
        ])
    else:
        keyboard.append([
            InlineKeyboardButton(
                text="✅ Отметить выполнение сегодня",
                callback_data=f"log_{habit_id}"
            )
        ])

    # Ряд с управлением
    keyboard.append([
        InlineKeyboardButton(text="📊 Статистика", callback_data=f"stats_{habit_id}"),
        InlineKeyboardButton(text="📝 Пометки по дням", callback_data=f"logdata_{habit_id}")
    ])

    keyboard.append([
        InlineKeyboardButton(text="✏️ Изменить", callback_data=f"edit_{habit_id}"),
        InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"delete_{habit_id}")
    ])

    # Кнопка возврата
    keyboard.append([
        InlineKeyboardButton(
            text="⬅️ Назад к списку",
            callback_data="back_to_list"
        )
    ])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# Клавиатура выбора типа привычки при создании.
def habit_type_selection_kb():
    """Клавиатура выбора типа привычки при создании."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Факт выполнения", callback_data="type_boolean")],
        [InlineKeyboardButton(text="🔢 Количество", callback_data="type_numeric")]
    ])

# Клавиатура выбора подписей для булевой привычки.
def habit_notes_selection_kb():
    """Клавиатура выбора подписей для булевой привычки."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да", callback_data="notes_yes")],
        [InlineKeyboardButton(text="❌ Нет", callback_data="notes_no")],
        [InlineKeyboardButton(text="🚫 Отмена", callback_data="cancel_new_habit")]
    ])

# Клавиатура подтверждения удаления привычки.
def delete_confirmation_kb(habit_id):
    """Клавиатура подтверждения удаления привычки."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"confirm_delete_{habit_id}"),
            InlineKeyboardButton(text="❌ Нет, отмена", callback_data=f"cancel_delete_{habit_id}")
        ]
    ])

# Клавиатура возврата из просмотра пометок в меню привычки.
def habit_notes_back_kb(habit_id):
    """Клавиатура возврата из просмотра пометок в меню привычки."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад к привычке", callback_data=f"habit_{habit_id}")]
    ])

# Клавиатура выбора периода статистики.
def stats_periods_kb(habit_id):
    """Клавиатура выбора периода статистики."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📈 7 дней", callback_data=f"statsperiod_{habit_id}_7")],
        [InlineKeyboardButton(text="📊 14 дней", callback_data=f"statsperiod_{habit_id}_14")],
        [InlineKeyboardButton(text="📉 31 день", callback_data=f"statsperiod_{habit_id}_31")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"habit_{habit_id}")]
    ])

# Клавиатура навигации в статистике
def stats_navigation_kb(habit_id):
    """Клавиатура навигации в статистике (смена периода + возврат)."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="7 дней", callback_data=f"statsperiod_{habit_id}_7"),
            InlineKeyboardButton(text="14 дней", callback_data=f"statsperiod_{habit_id}_14"),
            InlineKeyboardButton(text="31 день", callback_data=f"statsperiod_{habit_id}_31")
        ],
        [InlineKeyboardButton(text="⬅️ Назад к привычке", callback_data=f"habit_{habit_id}")]
    ])