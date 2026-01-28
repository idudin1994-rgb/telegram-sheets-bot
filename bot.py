import os
import re
import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import CommandStart
import gspread
from google.oauth2.service_account import Credentials

# ================= НАСТРОЙКИ =================

TOKEN = os.getenv("8257397371:AAFhMqkABmKhl0WwAe7-b7uuVoQf91dqUl0")
if not TOKEN:
    raise RuntimeError("TELEGRAM_TOKEN is not set")

SPREADSHEET_ID = "1Xw6sLPUOV3GVAwLGBL7IdCq5CyH6v1qFO3z9IS8NhH0"  # <-- ОБЯЗАТЕЛЬНО

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

creds = Credentials.from_service_account_file(
    "credentials.json",
    scopes=SCOPES
)
gc = gspread.authorize(creds)

bot = Bot(token=TOKEN)
dp = Dispatcher()

# ================= ПАМЯТЬ =================

users = {}

def get_user(uid: int):
    if uid not in users:
        users[uid] = {
            "step": "WAIT_TITLE",
            "event": {
                "title": "",
                "date_start": "",
                "date_end": "",
                "time_start": "",
                "time_end": "",
                "desc": ""
            }
        }
    return users[uid]

# ================= КНОПКИ =================

menu_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📅 Дата окончания"), KeyboardButton(text="⏰ Время начала")],
        [KeyboardButton(text="⏱ Время окончания"), KeyboardButton(text="📝 Описание")],
        [KeyboardButton(text="✅ Отправить")]
    ],
    resize_keyboard=True
)

# ================= GOOGLE SHEETS =================

def get_sheet():
    sh = gc.open_by_key(SPREADSHEET_ID)
    ws = sh.sheet1

    # если таблица пустая — создаём заголовки
    if ws.acell("A1").value is None:
        ws.append_row([
            "Название",
            "Дата начала",
            "Дата окончания",
            "Время начала",
            "Время окончания",
            "Описание"
        ])

    return ws

def save_event(event: dict):
    ws = get_sheet()
    ws.append_row([
        event["title"],
        event["date_start"],
        event["date_end"],
        event["time_start"],
        event["time_end"],
        event["desc"]
    ], value_input_option="USER_ENTERED")

# ================= ХЭНДЛЕРЫ =================

@dp.message(CommandStart())
async def start(msg: Message):
    users.pop(msg.from_user.id, None)
    get_user(msg.from_user.id)

    await msg.answer(
        "👋 Привет!\n\n"
        "Я записываю события в Google Таблицу.\n\n"
        "✏️ Введи *название события*:"
    )

@dp.message(F.text)
async def handler(msg: Message):
    uid = msg.from_user.id
    text = msg.text.strip()
    user = get_user(uid)

    # ---- НАЗВАНИЕ ----
    if user["step"] == "WAIT_TITLE":
        user["event"]["title"] = text
        user["step"] = "WAIT_DATE_START"
        await msg.answer("📅 Введи *дату начала* (например 01.02.2026):")
        return

    # ---- ДАТА НАЧАЛА ----
    if user["step"] == "WAIT_DATE_START":
        user["event"]["date_start"] = text
        user["step"] = "MENU"
        await msg.answer("Что добавить дальше? 👇", reply_markup=menu_kb)
        return

    # ---- МЕНЮ ----
    if user["step"] == "MENU":

        if text == "📅 Дата окончания":
            user["step"] = "WAIT_DATE_END"
            await msg.answer("📅 Введи дату окончания:")
            return

        if text == "⏰ Время начала":
            user["step"] = "WAIT_TIME_START"
            await msg.answer("⏰ Введи время начала (ЧЧ:ММ):")
            return

        if text == "⏱ Время окончания":
            user["step"] = "WAIT_TIME_END"
            await msg.answer("⏱ Введи время окончания (ЧЧ:ММ):")
            return

        if text == "📝 Описание":
            user["step"] = "WAIT_DESC"
            await msg.answer("📝 Введи описание:")
            return

        if text == "✅ Отправить":
            save_event(user["event"])
            await msg.answer("✅ Событие сохранено!")
            users.pop(uid, None)
            return

    # ---- ДОП ПОЛЯ ----
    if user["step"] == "WAIT_DATE_END":
        user["event"]["date_end"] = text
        user["step"] = "MENU"
        await msg.answer("Готово 👌", reply_markup=menu_kb)
        return

    if user["step"] == "WAIT_TIME_START":
        user["event"]["time_start"] = text
        user["step"] = "MENU"
        await msg.answer("Готово 👌", reply_markup=menu_kb)
        return

    if user["step"] == "WAIT_TIME_END":
        user["event"]["time_end"] = text
        user["step"] = "MENU"
        await msg.answer("Готово 👌", reply_markup=menu_kb)
        return

    if user["step"] == "WAIT_DESC":
        user["event"]["desc"] = text
        user["step"] = "MENU"
        await msg.answer("Готово 👌", reply_markup=menu_kb)
        return

# ================= ЗАПУСК =================

async def main():
    print("Bot started")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
