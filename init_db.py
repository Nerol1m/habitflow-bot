from bot.database.engine import engine
from bot.database.models import Base
import asyncio

async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Таблицы созданы!")

if __name__ == "__main__":
    asyncio.run(create_tables())