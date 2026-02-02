import asyncio
import logging
from aiogram import Bot, Dispatcher
from config import BOT_TOKEN

# Импортируем роутеры
from bot.handlers.start import router as start_router
from bot.handlers.habits import router as habits_router
from bot.handlers.settings import router as settings_router

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Подключаем роутеры
dp.include_router(start_router)
dp.include_router(habits_router)
dp.include_router(settings_router)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())