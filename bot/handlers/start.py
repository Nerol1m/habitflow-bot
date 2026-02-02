from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from bot.keyboards.reply import main_kb
from bot.database.models import User
from bot.database.engine import async_session_maker
from sqlalchemy import select

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message):
    try:
        async with async_session_maker() as session:
            async with session.begin():
                # Проверяем, есть ли пользователь
                existing = await session.execute(
                    select(User).where(User.telegram_id == message.from_user.id)
                )
                user = existing.scalar_one_or_none()

                # Если нет — регистрируем
                if not user:
                    user = User(
                        telegram_id=message.from_user.id,
                        username=message.from_user.username,
                        full_name=f"{message.from_user.first_name} {message.from_user.last_name or ''}".strip(),
                    )
                    session.add(user)
                    # commit() вызывается автоматически при выходе из блока

        await message.answer(
            f"Привет, {message.from_user.first_name}! 👋\nЯ твой помощник в формировании привычек.",
            reply_markup=main_kb()
        )

    except Exception as e:
        await message.answer("Произошла ошибка. Попробуйте позже.")
        print(f"Error: {e}")