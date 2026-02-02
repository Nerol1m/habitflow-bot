from sqlalchemy import BigInteger, String, Text, DateTime, Boolean
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from datetime import datetime, date
from sqlalchemy import ForeignKey, Date
import enum

class Base(DeclarativeBase):
    pass


class HabitType(enum.Enum):
    BOOLEAN = "boolean"
    NUMERIC = "numeric"


class Habit(Base):
    __tablename__ = "habits"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    allow_notes: Mapped[bool] = mapped_column(Boolean, default=False)
    habit_type: Mapped[str] = mapped_column(String(10), default="boolean")
    numeric_unit: Mapped[str] = mapped_column(String(20), nullable=True)


class HabitLog(Base):
    __tablename__ = "habit_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    habit_id: Mapped[int] = mapped_column(ForeignKey("habits.id"))  # связь с привычкой
    date: Mapped[date] = mapped_column(Date, default=datetime.utcnow().date)
    completed: Mapped[bool] = mapped_column(Boolean, default=True)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str] = mapped_column(String(100), nullable=True)
    full_name: Mapped[str] = mapped_column(String(200))
    registered_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    # для напоминаний:
    timezone: Mapped[str] = mapped_column(String(50), default='UTC')
    reminders_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    reminder_time: Mapped[str] = mapped_column(String(5), default="09:00")
    reminder_task_id: Mapped[str] = mapped_column(String(100), nullable=True)


class HabitNote(Base):
    __tablename__ = "habit_notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    log_id: Mapped[int] = mapped_column(ForeignKey("habit_logs.id"))
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)