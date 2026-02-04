from datetime import datetime, timedelta
import pytz
from .celery_app import celery_app
import requests, redis
import os


@celery_app.task
def send_reminder(user_id: int, text: str):
    token = os.getenv('BOT_TOKEN')
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = {"chat_id": user_id, "text": text, "parse_mode": "HTML"}

    try:
        response = requests.post(url, json=data, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"Ошибка отправки напоминания: {e}")
        return False


def parse_timezone(tz_str: str):
    """Конвертирует строку типа UTC+3 в формат pytz"""
    if tz_str.startswith('UTC'):
        offset = int(tz_str[3:])
        if offset > 0:
            return f'Etc/GMT-{offset}'
        elif offset < 0:
            return f'Etc/GMT+{abs(offset)}'
        else:
            return 'UTC'
    return tz_str


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
    """Планирует одно напоминание на указанное время"""
    try:
        tz = pytz.timezone(parse_timezone(timezone))
        now = datetime.now(tz)

        target_time = datetime.strptime(reminder_time, "%H:%M").time()
        target_dt = tz.localize(datetime.combine(now.date(), target_time))

        if target_dt < now:
            target_dt += timedelta(days=1)

        utc_time = target_dt.astimezone(pytz.UTC)
        seconds_until = (utc_time - datetime.now(pytz.UTC)).total_seconds()

        if seconds_until > 0:
            send_reminder.apply_async(
                args=[user_id, "⏰ Время отмечать привычки!"],
                countdown=int(seconds_until)
            )
            return True
        return False

    except Exception as e:
        print(f"Ошибка планирования напоминания: {e}")
        return False


@celery_app.task
def cancel_user_reminders(user_id: int):
    """Отмечает отмену напоминаний"""
    return True
