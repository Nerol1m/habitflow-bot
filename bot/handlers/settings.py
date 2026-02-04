import re

from aiogram import Router
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from bot.database.engine import async_session_maker
from bot.database.models import User
from sqlalchemy import select
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from bot.keyboards.reply import main_kb
from bot.keyboards.inline import settings_kb, timezone_selection_kb, time_selection_kb
from celery_worker.tasks import schedule_user_reminder, cancel_user_reminders

router = Router()

class SettingsForm(StatesGroup):
    waiting_for_custom_timezone = State()
    waiting_for_custom_time = State()

@router.message(lambda message: message.text == '⚙️ Настройки')
@router.message(Command('settings'))
async def cmd_settings(message: Message):
    async with async_session_maker() as session:
        user = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        user = user.scalar_one_or_none()

    if not user:
        return

    text = (
        "<b>⚙️ Настройки</b>\n\n"
        f"• ID: <code>{user.telegram_id}</code>\n"
        f"• Зарегистрирован: {user.registered_at.strftime('%d.%m.%Y')}\n"
        f"• Часовой пояс: <b>{user.timezone}</b>\n\n"
        "Здесь позже можно будет изменить время напоминаний."
    )

    keyboard = settings_kb(user)

    await message.answer(text, parse_mode="HTML", reply_markup=keyboard)

@router.callback_query(lambda c: c.data == "change_timezone")
async def change_timezone_start(callback: CallbackQuery):
    keyboard = timezone_selection_kb()

    await callback.message.edit_text(
        "Выберите ваш часовой пояс:\n(Нужен для правильного времени напоминаний)",
        reply_markup=keyboard
    )
    await callback.answer()

@router.callback_query(lambda c: c.data.startswith("tz_"))
async def change_timezone_finish(callback: CallbackQuery, state: FSMContext):
    tz_value = callback.data.replace("tz_", "")

    if tz_value == "custom":
        await callback.message.answer("Введите ваш часовой пояс в формате UTC±XX (например, UTC+5):")
        await state.set_state(SettingsForm.waiting_for_custom_timezone)
        return

    async with async_session_maker() as session:
        user = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = user.scalar_one()
        user.timezone = tz_value
        await session.commit()

    await callback.message.edit_text(
        f"✅ Часовой пояс изменён на <b>{tz_value}</b>",
        parse_mode="HTML"
    )
    await callback.answer()

@router.message(SettingsForm.waiting_for_custom_timezone)
async def process_custom_timezone_input(message: Message, state: FSMContext):
    tz_pattern = r'^UTC([+-])(0?[0-9]|1[0-4])$'
    match = re.match(tz_pattern, message.text.strip())

    if not match:
        await message.answer(
            "❌ Неверный формат.\n"
            "Пожалуйста, введите в формате UTC±XX (например, UTC+5 или UTC-3):\n"
            "Диапазон: от UTC-12 до UTC+14."
        )
        return

    sign, hours = match.groups()
    tz_value = f"UTC{sign}{int(hours):02d}"

    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        user = result.scalar_one()
        user.timezone = tz_value
        await session.commit()

    await state.clear()

    keyboard = settings_kb(user)

    await message.answer(
        f"✅ Часовой пояс изменён на <b>{tz_value}</b>\n"
        f"Все напоминания будут приходить по этому времени.",
        parse_mode="HTML",
        reply_markup=keyboard
    )

@router.callback_query(lambda c: c.data == "change_reminder_time")
async def change_reminder_time_start(callback: CallbackQuery):
    keyboard = time_selection_kb()

    await callback.message.edit_text(
        "Выберите время для ежедневных напоминаний (по вашему часовому поясу):",
        reply_markup=keyboard
    )
    await callback.answer()

@router.callback_query(lambda c: c.data.startswith("remtime_"))
async def change_reminder_time_finish(callback: CallbackQuery, state: FSMContext):
    time_value = callback.data.replace("remtime_", "")

    if time_value == "custom":
        await callback.message.answer(
            "Введите время в формате ЧЧ:ММ (например, 08:30):\n"
            "Я напомню вам отмечать привычки в это время каждый день."
        )
        await state.set_state(SettingsForm.waiting_for_custom_time)
        return

    if not re.match(r'^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$', time_value):
        await callback.answer("❌ Неверный формат времени. Используйте ЧЧ:ММ", show_alert=True)
        return

    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one()
        user.reminder_time = time_value
        await session.commit()

    cancel_user_reminders.delay(user_id=callback.from_user.id)
    if user.reminders_enabled:
        schedule_user_reminder.delay(
            user_id=callback.from_user.id,
            reminder_time=time_value,
            timezone=user.timezone
        )

    await callback.message.edit_text(
        f"✅ Время напоминаний изменено на <b>{time_value}</b>\n"
        f"Я буду напоминать вам каждый день в это время ({user.timezone}).",
        parse_mode="HTML"
    )
    await callback.answer()

@router.message(SettingsForm.waiting_for_custom_time)
async def process_custom_time_input(message: Message, state: FSMContext):
    time_pattern = r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$'

    if not re.match(time_pattern, message.text):
        await message.answer(
            "❌ Неверный формат времени.\n"
            "Пожалуйста, введите время в формате ЧЧ:ММ (например, 09:00 или 21:30):"
        )
        return

    time_value = message.text

    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        user = result.scalar_one()
        user.reminder_time = time_value
        await session.commit()

    cancel_user_reminders.delay(user_id=message.from_user.id)
    if user.reminders_enabled:
        schedule_user_reminder.delay(
            user_id=message.from_user.id,
            reminder_time=time_value,
            timezone=user.timezone
        )

    await state.clear()

    keyboard = settings_kb(user, time_value)

    await message.answer(
        f"✅ Время напоминаний установлено на <b>{time_value}</b>\n\n"
        f"Теперь я буду напоминать вам каждый день в это время ({user.timezone}).",
        parse_mode="HTML",
        reply_markup=keyboard
    )

@router.callback_query(lambda c: c.data == "toggle_reminders")
async def toggle_reminders(callback: CallbackQuery):
    async with async_session_maker() as session:
        user = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = user.scalar_one()

        new_status = not user.reminders_enabled
        user.reminders_enabled = new_status

        if new_status:
            schedule_user_reminder.delay(
                user_id=callback.from_user.id,
                reminder_time=user.reminder_time,
                timezone=user.timezone
            )
        else:
            cancel_user_reminders.delay(user_id=callback.from_user.id)

        await session.commit()

        status = "включены" if new_status else "выключены"

    await callback.message.edit_text(
        f"✅ Напоминания <b>{status}</b>\n\n"
        f"Сейчас они приходят в <b>{user.reminder_time}</b> по вашему времени ({user.timezone}).",
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(lambda c: c.data == "back_to_main")
async def back_to_main_settings(callback: CallbackQuery):
    await callback.message.answer(
        "Главное меню:",
        reply_markup=main_kb(),
        parse_mode="HTML"
    )
    await callback.message.delete()
    await callback.answer()