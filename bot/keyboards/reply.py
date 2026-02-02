from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def main_kb():
    kb = [
        [KeyboardButton(text='📝 Новая привычка'), KeyboardButton(text='📋 Мои привычки')],
        [KeyboardButton(text='📊 Общая статистика'), KeyboardButton(text='⚙️ Настройки')],
        [KeyboardButton(text='❓ Помощь')]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)