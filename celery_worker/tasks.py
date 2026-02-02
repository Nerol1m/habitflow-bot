from datetime import datetime, timedelta
import pytz
from .celery_app import celery_app


@celery_app.task
def send_reminder(user_id: int, text: str):
    print(f"НАПОМИНАНИЕ пользователю {user_id}: {text}")
    return True


def parse_timezone(tz_str: str):
    """Конвертирует UTC+3 в формат для pytz"""
    if tz_str.startswith('UTC'):
        offset = int(tz_str[3:])
        if offset > 0:
            return f'Etc/GMT-{offset}'  # UTC+3 -> Etc/GMT-3
        elif offset < 0:
            return f'Etc/GMT+{abs(offset)}'  # UTC-5 -> Etc/GMT+5
        else:
            return 'UTC'
    return tz_str  # Оставляем как есть если не UTC


async def update_user_task_id(user_id: int, task_id: str):
    """Сохраняет ID задачи в БД"""
    from bot.database.engine import async_session_maker
    from bot.database.models import User
    from sqlalchemy import update

    async with async_session_maker() as session:
        await session.execute(
            update(User)
            .where(User.telegram_id == user_id)
            .values(reminder_task_id=task_id)
        )
        await session.commit()


@celery_app.task
def schedule_user_reminder(user_id: int, reminder_time: str, timezone: str):
    """Планирует ежедневное напоминание для пользователя"""
    try:
        tz = pytz.timezone(parse_timezone(timezone))

        now = datetime.now(tz)
        target_time = datetime.strptime(reminder_time, "%H:%M").time()
        target_dt = tz.localize(datetime.combine(now.date(), target_time))

        if target_dt < now:
            target_dt += timedelta(days=1)

        utc_time = target_dt.astimezone(pytz.UTC)

        send_reminder.apply_async(
            args=[user_id, "⏰ Время отмечать привычки!"],
            eta=utc_time
        )

        print(f"✅ Напоминание для {user_id} на {utc_time}")
        return True

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False