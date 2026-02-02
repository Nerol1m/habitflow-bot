from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.exceptions import TelegramBadRequest


from bot.database.models import Habit
from bot.database.engine import async_session_maker
from bot.keyboards.reply import main_kb
from bot.keyboards.inline import habits_list_kb, habit_menu_kb, habit_type_selection_kb, habit_notes_selection_kb, delete_confirmation_kb
from bot.keyboards.inline import habit_notes_back_kb, stats_periods_kb, stats_navigation_kb
from bot.database.models import HabitLog, HabitNote

from sqlalchemy import select, delete, func
from datetime import datetime, timedelta

import matplotlib.pyplot as plt
import io
import re

router = Router()


class HabitForm(StatesGroup):
    waiting_for_name = State()
    waiting_for_habit_type = State()
    waiting_for_numeric_unit = State()
    waiting_for_notes_choice = State()

class HabitLogForm(StatesGroup):
    waiting_for_note = State()

class EditHabitForm(StatesGroup):
    waiting_for_new_name = State()

class NumericLogForm(StatesGroup):
    waiting_for_numeric_value = State()




# Функция расчёта стрика
async def calculate_streak(session, habit_id: int) -> int:
    logs = await session.execute(
        select(HabitLog.date)
        .where(HabitLog.habit_id == habit_id, HabitLog.completed == True)
        .order_by(HabitLog.date.desc())
    )
    dates = [log[0] for log in logs.fetchall()]

    if not dates:
        return 0

    today = datetime.utcnow().date()
    streak = 0

    # Проверяем последовательность дней от сегодня назад
    expected_date = today
    for log_date in dates:
        if log_date == expected_date:
            streak += 1
            expected_date -= timedelta(days=1)
        else:
            break

    return streak


# Меню всех привычек
async def build_habits_message(session, user_id: int):
    habits = await session.execute(
        select(Habit).where(
            Habit.user_id == user_id,
            Habit.is_active == True
        )
    )
    habits = habits.scalars().all()

    if not habits:
        return "📭 У тебя пока нет активных привычек.", None

    text = "📋 Твои привычки (нажми для управления):\n\n"

    habits_data = []
    for habit in habits:
        streak = await calculate_streak(session, habit.id)
        streak_text = f" 🔥{streak}" if streak > 0 else ""
        habits_data.append((habit, streak_text))

    keyboard = habits_list_kb(habits_data)

    return text, keyboard


# Меню управления конкретной привычки
async def build_habit_menu(session, habit: Habit):
    streak = await calculate_streak(session, habit.id)
    today = datetime.utcnow().date()

    # Проверяем, отмечена ли сегодня
    today_log = await session.execute(
        select(HabitLog).where(
            HabitLog.habit_id == habit.id,
            HabitLog.date == today
        )
    )
    is_today_logged = bool(today_log.scalar())

    text = f"<b>🏷️ {habit.name}</b>\n"
    if habit.description:
        text += f"📝 {habit.description}\n"
    text += f"\n📊 Серия: {streak} день(ей) подряд\n"
    text += f"📅 Создана: {habit.created_at.strftime('%d.%m.%Y')}\n\n"

    # Клавиатура
    keyboard = habit_menu_kb(habit.id, is_today_logged)

    return text, keyboard


# Генерирует график выполнения привычки за указанное количество дней
async def generate_habit_chart(habit: Habit, days: int) -> io.BytesIO:
    async with async_session_maker() as session:
        end_date = datetime.utcnow().date()
        start_date = end_date - timedelta(days=days-1)

        logs = await session.execute(
            select(HabitLog.date, HabitNote.text)
            .outerjoin(HabitNote, HabitLog.id == HabitNote.log_id)
            .where(
                HabitLog.habit_id == habit.id,
                HabitLog.date >= start_date,
                HabitLog.date <= end_date
            )
            .order_by(HabitLog.date)
        )
        log_data = logs.fetchall()

        # Подготовка данных
        dates = [start_date + timedelta(days=i) for i in range(days)]
        values = []
        labels = []

        for date in dates:
            record = next((log for log in log_data if log[0] == date), None)
            if record:
                if habit.habit_type == "numeric":
                    note_text = record[1] or ""
                    num = re.search(r'\d+', note_text)
                    value = int(num.group()) if num else 1
                else:
                    value = 1
                label = record[1] or "Выполнено"
            else:
                value = 0
                label = "Нет"
            values.append(value)
            labels.append(label)

        # ПОСТРОЕНИЕ ГРАФИКА
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8),
                                        height_ratios=[1, 3] if habit.habit_type == "numeric" else [1, 2])
        fig.suptitle(f'Статистика: {habit.name}', fontsize=16)

        # ВЕРХНИЙ ГРАФИК
        if habit.habit_type == "numeric":
            cumulative = [sum(values[:i+1]) for i in range(days)]
            ax1.plot(range(days), cumulative, color='#339af0', linewidth=2, marker='o')
            ax1.fill_between(range(days), cumulative, alpha=0.2, color='#339af0')
            ax1.set_ylabel('Накоплено', fontsize=10)
            ax1.grid(True, alpha=0.3)
            ax1.set_title(f'Прогресс за {days} дней', fontsize=12)
        else:
            completed = sum(1 for v in values if v > 0)
            percentage = (completed / days) * 100 if days > 0 else 0
            ax1.bar(['Выполнено'], [percentage], color='#51cf66')
            ax1.bar(['Пропущено'], [100 - percentage], bottom=[percentage], color='#ff6b6b')
            ax1.set_ylim(0, 100)
            ax1.set_ylabel('Процент (%)', fontsize=10)
            ax1.set_title(f'Выполнено: {completed}/{days} дней ({percentage:.1f}%)', fontsize=12)

        # НИЖНИЙ ГРАФИК (разный для типов привычек)
        if habit.habit_type == "numeric":
            # ЧИСЛОВАЯ
            colors = ['#51cf66' if v > 0 else '#ff6b6b' for v in values]
            bars = ax2.bar(range(days), values, color=colors, edgecolor='white', linewidth=1)
            for bar, val in zip(bars, values):
                if val > 0:
                    ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.1,
                            str(val), ha='center', va='bottom', fontsize=9)
            ax2.set_xlabel('Дни', fontsize=10)
            ax2.set_ylabel(f'Количество ({habit.numeric_unit or "ед."})', fontsize=10)
            from matplotlib.patches import Patch
            legend_elements = [Patch(facecolor='#51cf66', label='Выполнено'),
                             Patch(facecolor='#ff6b6b', label='Пропущено')]
            ax2.legend(handles=legend_elements, loc='upper left')
        else:
            # БУЛЕВАЯ
            colors = ['#51cf66' if v > 0 else '#ff6b6b' for v in values]
            ax2.bar(range(days), [1] * days, color=colors, edgecolor='white', linewidth=1)
            ax2.set_ylim(0, 1.2)
            ax2.set_xlabel('Дни', fontsize=10)
            ax2.set_ylabel('Факт', fontsize=10)
            ax2.set_yticks([0, 1])
            ax2.set_yticklabels(['Нет', 'Да'])

        # Общие настройки для нижнего графика
        ax2.set_xticks(range(days))
        ax2.set_xticklabels([d.strftime('%d.%m') for d in dates], rotation=45, fontsize=9)
        ax2.grid(True, alpha=0.3, axis='y')

        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=100)
        plt.close()
        buf.seek(0)
        return buf


# Безопасно обновляет сообщение: редактирует или переотправляет при ошибке.
async def safe_edit_message(callback, text, keyboard, parse_mode="HTML"):
    """
    Безопасно обновляет сообщение: редактирует или переотправляет при ошибке.
    """
    if callback.message.photo:
        await callback.message.delete()
        await callback.message.answer(text, reply_markup=keyboard, parse_mode=parse_mode)
    else:
        try:
            await callback.message.edit_text(text, reply_markup=keyboard, parse_mode=parse_mode)
        except TelegramBadRequest:
            await callback.message.delete()
            await callback.message.answer(text, reply_markup=keyboard, parse_mode=parse_mode)



# 1. Команды
# /new
@router.message(Command('new'))
async def cmd_new(message: Message, state: FSMContext):
    await message.answer("📝 Введи название новой привычки:", reply_markup=main_kb())
    await state.set_state(HabitForm.waiting_for_name)

# /list
@router.message(Command('list'))
async def cmd_list(message: Message):
    async with async_session_maker() as session:
        text, keyboard = await build_habits_message(session, message.from_user.id)

    if text is None:
        await message.answer("📭 У тебя пока нет активных привычек.")
        return

    await message.answer(text, reply_markup=keyboard)



# 2. Reply кнопки
@router.message(lambda message: message.text == '📋 Мои привычки')
async def btn_list_habits(message: Message):
    await cmd_list(message)

@router.message(lambda message: message.text == '📝 Новая привычка')
async def btn_new_habit(message: Message, state: FSMContext):
    await cmd_new(message, state)

@router.message(lambda message: message.text == '❓ Помощь')
async def btn_help(message: Message):
    help_text = (
        "<b>🆘 Помощь по боту</b>\n\n"
        "<i>📝 Новая привычка</i> – создать привычку\n"
        "<i>📋 Все привычки</i> – список привычек\n"
        "<i>📊 Общая статистика</i> – прогресс по всем привычкам\n"
        "<i>⚙️ Настройки</i> – время напоминаний, часовой пояс\n\n"
        "<b>📌 Внутри привычки:</b>\n"
        "✅ – отметить выполнение\n"
        "📊 – статистика привычки\n"
        "✏️ – изменить название\n"
        "🗑️ – удалить привычку"
    )
    await message.answer(help_text, parse_mode="HTML", reply_markup=main_kb())

@router.message(lambda message: message.text == '📊 Общая статистика')
async def btn_general_stats(message: Message):
    user_id = message.from_user.id

    async with async_session_maker() as session:
        # Получаем все привычки пользователя
        habits = await session.execute(
            select(Habit).where(Habit.user_id == user_id, Habit.is_active == True)
        )
        habits = habits.scalars().all()

        if not habits:
            await message.answer("📭 У вас пока нет активных привычек.")
            return

        # Считаем общую статистику
        total_habits = len(habits)
        total_numeric = sum(1 for h in habits if h.habit_type == "numeric")
        total_boolean = total_habits - total_numeric

        # Считаем общее количество выполненных дней за последнюю неделю
        week_ago = datetime.utcnow().date() - timedelta(days=7)
        completed_logs = await session.execute(
            select(func.count(HabitLog.id))
            .join(Habit, Habit.id == HabitLog.habit_id)
            .where(Habit.user_id == user_id, HabitLog.date >= week_ago)
        )
        completed_last_week = completed_logs.scalar() or 0

        text = (
            "<b>📊 Общая статистика</b>\n\n"
            f"• Всего привычек: <b>{total_habits}</b>\n"
            f"• Из них числовых: <b>{total_numeric}</b>\n"
            f"• Факт выполнения: <b>{total_boolean}</b>\n\n"
            f"• Выполнено за 7 дней: <b>{completed_last_week}</b> раз\n"
            f"• В среднем в день: <b>{completed_last_week / 7:.1f}</b>"
        )

    await message.answer(text, parse_mode="HTML")



# 3. Callback обработчики:
## habit_ меню
# Обработчик перехода к привычке
@router.callback_query(lambda c: c.data.startswith("habit_"))
async def show_habit_menu(callback: CallbackQuery):
    habit_id = int(callback.data.split("_")[1])

    async with async_session_maker() as session:
        habit = await session.get(Habit, habit_id)
        if not habit:
            await callback.answer("Привычка не найдена")
            return

        if habit.user_id != callback.from_user.id:
            await callback.answer("Это не твоя привычка")
            return

        text, keyboard = await build_habit_menu(session, habit)

    await safe_edit_message(callback, text, keyboard, parse_mode="HTML")
    await callback.answer()

# Обработчик back_to_list
@router.callback_query(lambda c: c.data == "back_to_list")
async def back_to_list(callback: CallbackQuery):
    async with async_session_maker() as session:
        text, keyboard = await build_habits_message(session, callback.from_user.id)

    await safe_edit_message(callback, text, keyboard, parse_mode="HTML")
    await callback.answer()

# Обработка новой привычки
@router.callback_query(lambda c: c.data == "new_habit")
async def new_habit_from_button(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("📝 Введи название новой привычки:")
    await state.set_state(HabitForm.waiting_for_name)
    await callback.answer()

# Обработчик отмены создания привычки
@router.callback_query(lambda c: c.data == "cancel_new_habit")
async def cancel_new_habit(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Создание привычки отменено.")
    await callback.answer()


## log_ отметки
# Обработчик отметки привычки.
@router.callback_query(lambda c: c.data.startswith("log_"))
async def process_habit_log(callback: CallbackQuery, state: FSMContext):
    habit_id = int(callback.data.split("_")[1])
    today = datetime.utcnow().date()

    async with async_session_maker() as session:
        # Получаем привычку
        habit = await session.get(Habit, habit_id)
        if not habit:
            await callback.answer("Привычка не найдена")
            return

        # Проверяем, не отмечена ли уже сегодня
        existing = await session.execute(
            select(HabitLog).where(
                HabitLog.habit_id == habit_id,
                HabitLog.date == today
            )
        )
        if existing.scalar():
            await callback.answer("✅ Уже отмечено сегодня!")
            return

        # 1. Если разрешены подписи (только для булевых привычек)
        if habit.allow_notes and habit.habit_type == "boolean":
            await state.update_data(
                habit_id=habit_id,
                today=today.isoformat()
            )
            await callback.message.answer("📝 Добавь подпись к отметке (или отправь '-' для пропуска):")
            await state.set_state(HabitLogForm.waiting_for_note)
            await callback.answer()
            return

        # 2. Если числовая привычка (с подписями или без)
        if habit.habit_type == "numeric":
            await state.update_data(
                habit_id=habit_id,
                today=today.isoformat()
            )
            unit = habit.numeric_unit or "раз"
            await callback.message.answer(f"Введите количество ({unit}):")
            await state.set_state(NumericLogForm.waiting_for_numeric_value)
            await callback.answer()
            return

        # 3. Булевая привычка без подписей (просто отмечаем)
        log = HabitLog(habit_id=habit_id, date=today)
        session.add(log)
        await session.commit()

        # Возвращаемся в меню привычки
        text, keyboard = await build_habit_menu(session, habit)

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer("✅ Отмечено!")

@router.callback_query(lambda c: c.data.startswith("unlog_"))
async def process_habit_unlog(callback: CallbackQuery):
    habit_id = int(callback.data.split("_")[1])
    today = datetime.utcnow().date()

    async with async_session_maker() as session:
        log_result = await session.execute(
            select(HabitLog.id).where(
                HabitLog.habit_id == habit_id,
                HabitLog.date == today
            )
        )
        log_id = log_result.scalar()

        if not log_id:
            await callback.answer("Запись не найдена.")
            return

        await session.execute(
            delete(HabitNote).where(HabitNote.log_id == log_id)
        )

        await session.execute(
            delete(HabitLog).where(HabitLog.id == log_id)
        )

        await session.commit()

        habit = await session.get(Habit, habit_id)
        text, keyboard = await build_habit_menu(session, habit)

    await safe_edit_message(callback, text, keyboard)
    await callback.answer("✅ Отмена отметки!")



## delete_
# Удаление привычки
@router.callback_query(lambda c: c.data.startswith("delete_"))
async def delete_habit_handler(callback: CallbackQuery):
    habit_id = int(callback.data.split("_")[1])

    # Клавиатура подтверждения
    confirm_keyboard = delete_confirmation_kb(habit_id)

    # Запрашиваем подтверждение
    await callback.message.edit_text(
        "❓ Точно удалить эту привычку?\nВсе записи о её выполнении также удалятся.",
        reply_markup=confirm_keyboard
    )
    await callback.answer()

# Подтверждение удаления
@router.callback_query(lambda c: c.data.startswith("confirm_delete_"))
async def confirm_delete_habit(callback: CallbackQuery):
    habit_id = int(callback.data.split("_")[2])
    user_id = callback.from_user.id

    async with async_session_maker() as session:
        logs = await session.execute(
            select(HabitLog.id).where(HabitLog.habit_id == habit_id)
        )
        log_ids = [log[0] for log in logs.fetchall()]

        if log_ids:
            await session.execute(
                delete(HabitNote).where(HabitNote.log_id.in_(log_ids))
            )

        await session.execute(delete(HabitLog).where(HabitLog.habit_id == habit_id))

        await session.execute(delete(Habit).where(Habit.id == habit_id))

        await session.commit()

        text, keyboard = await build_habits_message(session, user_id)

    await callback.message.edit_text(
        text or "✅ Привычка удалена!",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback.answer("🗑️ Привычка удалена")

# Отмена удаления
@router.callback_query(lambda c: c.data.startswith("cancel_delete_"))
async def cancel_delete_habit(callback: CallbackQuery):
    habit_id = int(callback.data.split("_")[2])

    async with async_session_maker() as session:
        habit = await session.get(Habit, habit_id)
        if habit:
            # Возвращаемся в меню привычки
            text, keyboard = await build_habit_menu(session, habit)
            await safe_edit_message(callback, text, keyboard, parse_mode="HTML")

    await callback.answer("❌ Удаление отменено")


## stats_ статистика
# Обработчик статистики
@router.callback_query(lambda c: c.data.startswith("stats_"))
async def show_stats_periods(callback: CallbackQuery):
    habit_id = int(callback.data.split("_")[1])

    keyboard = stats_periods_kb(habit_id)

    await callback.message.edit_text(
        "Выберите период для статистики:",
        reply_markup=keyboard
    )
    await callback.answer()

# Обработчик периода статистики
@router.callback_query(lambda c: c.data.startswith("statsperiod_"))
async def show_habit_stats(callback: CallbackQuery):
    await callback.answer()
    parts = callback.data.split("_")
    habit_id = int(parts[1])
    days = int(parts[2])

    async with async_session_maker() as session:
        habit = await session.get(Habit, habit_id)
        end_date = datetime.utcnow().date()
        start_date = end_date - timedelta(days=days - 1)

        # Получаем все логи за период
        logs = await session.execute(
            select(HabitLog.date)
            .where(
                HabitLog.habit_id == habit_id,
                HabitLog.date >= start_date,
                HabitLog.date <= end_date
            )
            .order_by(HabitLog.date)
        )
        log_dates = [log[0] for log in logs.fetchall()]

        # Считаем статистику
        total_days = days
        completed_days = len(log_dates)
        completion_rate = int((completed_days / total_days) * 100) if total_days > 0 else 0

        # Текущий стрик
        current_streak = await calculate_streak(session, habit_id)

        # Формируем текстовую статистику
        text = f"📊 <b>Статистика: {habit.name}</b>\n"
        text += f"📅 Период: {days} дней\n\n"
        text += f"✅ Выполнено: {completed_days}/{total_days} дней\n"
        text += f"📈 Процент выполнения: {completion_rate}%\n"
        text += f"🔥 Текущая серия: {current_streak} дней\n\n"

        chart_buffer = await generate_habit_chart(habit, days)

    # Кнопки
    keyboard = stats_navigation_kb(habit_id)

    # Отправляем фото с графиком
    await callback.message.answer_photo(
        BufferedInputFile(chart_buffer.getvalue(), filename='heatmap.png'),
        caption=text,
        parse_mode="HTML",
        reply_markup=keyboard
    )

    await callback.message.delete()
    await callback.answer()


## edit_ редактирование
# Обработчик изменений в привычке
@router.callback_query(lambda c: c.data.startswith("edit_"))
async def start_edit_habit(callback: CallbackQuery, state: FSMContext):
    habit_id = int(callback.data.split("_")[1])

    # Сохраняем ID привычки и текущее сообщение
    await state.update_data(
        habit_id=habit_id,
        message_id=callback.message.message_id
    )

    # Просим ввести новое название
    await callback.message.answer("Введите новое название привычки:")
    await state.set_state(EditHabitForm.waiting_for_new_name)
    await callback.answer()


## logdata_ пометки
# Обработчик пометок к привычке
@router.callback_query(lambda c: c.data.startswith("logdata_"))
async def show_habit_notes(callback: CallbackQuery):
    habit_id = int(callback.data.split("_")[1])

    async with async_session_maker() as session:
        # Получаем все логи с подписями для этой привычки
        notes = await session.execute(
            select(HabitLog.date, HabitNote.text)
            .join(HabitNote, HabitLog.id == HabitNote.log_id)
            .where(HabitLog.habit_id == habit_id)
            .order_by(HabitLog.date.desc())
            .limit(20)  # последние 20 записей
        )
        notes = notes.all()

        habit = await session.get(Habit, habit_id)

        if not notes:
            text = f"📝 Пометки к привычке «{habit.name}»\n\nПометок пока нет."
        else:
            text = f"📝 Пометки к привычке «{habit.name}»\n\n"
            for date, note_text in notes:
                text += f"• {date.strftime('%d.%m.%Y')}: {note_text}\n"

    # Кнопка возврата
    keyboard = habit_notes_back_kb(habit_id)

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


## notes_ выбор подписей
@router.callback_query(lambda c: c.data in ["notes_yes", "notes_no", "cancel_new_habit"])
async def process_notes_choice(callback: CallbackQuery, state: FSMContext):
    if callback.data == "cancel_new_habit":
        await state.clear()
        await callback.message.edit_text("❌ Создание привычки отменено.")
        await callback.answer()
        return

    data = await state.get_data()
    habit_name = data['habit_name']
    allow_notes = (callback.data == "notes_yes")
    habit_type_str = data.get('habit_type', 'type_boolean')
    numeric_unit = data.get('numeric_unit')

    habit_type_value = "numeric" if habit_type_str == 'type_numeric' else "boolean"

    async with async_session_maker() as session:
        habit = Habit(
            user_id=callback.from_user.id,
            name=habit_name,
            allow_notes=allow_notes,
            habit_type=habit_type_value,
            numeric_unit=numeric_unit
        )
        session.add(habit)
        await session.commit()

    note_text = "с подписями" if allow_notes else "без подписей"
    await callback.message.edit_text(f"✅ Привычка «{habit_name}» создана ({note_text})!")
    await state.clear()
    await callback.answer()



# 4. FSM обработчики
# Обработка названия
@router.message(HabitForm.waiting_for_name)
async def process_habit_name(message: Message, state: FSMContext):
    await state.update_data(habit_name=message.text)

    keyboard = habit_type_selection_kb()

    await message.answer(
        "Что отслеживаем?",
        reply_markup=keyboard
    )
    await state.set_state(HabitForm.waiting_for_habit_type)

# Обработка выбора типа
@router.callback_query(HabitForm.waiting_for_habit_type)
async def process_habit_type(callback: CallbackQuery, state: FSMContext):
    await state.update_data(habit_type=callback.data)

    if callback.data == "type_numeric":
        # Если число запрашиваем единицу измерения
        await callback.message.answer("Введите единицу измерения (например: 'раз', 'минут', 'страниц'):")
        await state.set_state(HabitForm.waiting_for_numeric_unit)
    else:
        # Если булевая спрашиваем про подписи
        keyboard = habit_notes_selection_kb()
        await callback.message.answer("Добавлять подписи к каждой отметке?", reply_markup=keyboard)
        await state.set_state(HabitForm.waiting_for_notes_choice)

    await callback.answer()

# Обработка единиц измерения
@router.message(HabitForm.waiting_for_numeric_unit)
async def process_numeric_unit(message: Message, state: FSMContext):
    data = await state.get_data()
    habit_name = data['habit_name']
    numeric_unit = message.text.strip()

    async with async_session_maker() as session:
        habit = Habit(
            user_id=message.from_user.id,
            name=habit_name,
            habit_type="numeric",
            numeric_unit=numeric_unit,
            allow_notes=False
        )
        session.add(habit)
        await session.commit()

    await message.answer(f"✅ Привычка «{habit_name}» создана (отслеживаем количество {numeric_unit})!")
    await state.clear()

# Обработчик для ввода подписи к отметке
@router.message(HabitLogForm.waiting_for_note)
async def process_habit_note(message: Message, state: FSMContext):
    data = await state.get_data()
    habit_id = data['habit_id']
    today = datetime.fromisoformat(data['today']).date()
    note_text = message.text.strip() if message.text.strip() != "-" else ""

    async with async_session_maker() as session:
        # Создаём запись о выполнении
        log = HabitLog(habit_id=habit_id, date=today)
        session.add(log)
        await session.flush()

        # Если подпись не пустая — сохраняем
        if note_text:
            note = HabitNote(log_id=log.id, text=note_text)
            session.add(note)

        await session.commit()

        # Возвращаемся в меню привычки
        habit = await session.get(Habit, habit_id)
        text, keyboard = await build_habit_menu(session, habit)

    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    await state.clear()

# Обработчик нового названия
@router.message(EditHabitForm.waiting_for_new_name)
async def finish_edit_habit(message: Message, state: FSMContext):
    data = await state.get_data()
    habit_id = data['habit_id']
    new_name = message.text.strip()

    if not new_name:
        await message.answer("Название не может быть пустым. Попробуйте ещё раз:")
        return

    async with async_session_maker() as session:
        # Получаем и обновляем привычку
        habit = await session.get(Habit, habit_id)
        if habit and habit.user_id == message.from_user.id:
            habit.name = new_name
            await session.commit()

            # Обновляем меню привычки
            text, keyboard = await build_habit_menu(session, habit)
            await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
        else:
            await message.answer("Ошибка: привычка не найдена.")

    await state.clear()

# Обработчик числа
@router.message(NumericLogForm.waiting_for_numeric_value)
async def process_numeric_value(message: Message, state: FSMContext):
    data = await state.get_data()
    habit_id = data['habit_id']
    today = datetime.fromisoformat(data['today']).date()

    try:
        value = int(message.text.strip())
        if value <= 0:
            raise ValueError
    except ValueError:
        await message.answer("Пожалуйста, введите целое положительное число:")
        return

    async with async_session_maker() as session:
        log = HabitLog(habit_id=habit_id, date=today)
        session.add(log)
        await session.flush()

        habit = await session.get(Habit, habit_id)
        unit = habit.numeric_unit or "раз"
        note_text = f"{value} {unit}"

        note = HabitNote(log_id=log.id, text=note_text)
        session.add(note)
        await session.commit()

        text, keyboard = await build_habit_menu(session, habit)

    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    await state.clear()