import os
import json
import logging
from datetime import datetime

from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup

import gspread
from oauth2client.service_account import ServiceAccountCredentials

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("8257397371:AAFhMqkABmKhl0WwAe7-b7uuVoQf91dqUl0")

GOOGLE_CREDS_FILE = "credentials.json"
SHEET_NAME = "Лист1"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())

# ===== Google Sheets =====
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]
creds = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_CREDS_FILE, scope)
gs_client = gspread.authorize(creds)

# ===== Хранилище пользователей =====
USERS_FILE = "users.json"

def load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    with open(USERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_users(users):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

def get_user(chat_id):
    users = load_users()
    return users.get(str(chat_id))

def set_user(chat_id, data):
    users = load_users()
    users[str(chat_id)] = data
    save_users(users)

# ===== States =====
class Form(StatesGroup):
    waiting_sheet = State()
    waiting_title = State()
    waiting_date_start = State()
    waiting_date_end = State()
    waiting_time_start = State()
    waiting_time_end = State()
    waiting_desc = State()

# ===== Helpers =====
def extract_sheet_id(url):
    import re
    m = re.search(r"/d/([a-zA-Z0-9-_]+)", url)
    return m.group(1) if m else None

def ensure_headers(sheet):
    if sheet.get_last_row() == 0:
        sheet.append_row([
            "Название",
            "Дата начала",
            "Дата окончания",
            "Время начала",
            "Время окончания",
            "Описание"
        ])

def normalize_date(text):
    text = text.strip()
    now = datetime.now()

    for fmt in ["%d.%m.%Y", "%d.%m.%y", "%d.%m"]:
        try:
            dt = datetime.strptime(text, fmt)
            if fmt == "%d.%m":
                dt = dt.replace(year=now.year)
            return dt.strftime("%d.%m.%Y")
        except:
            pass

    return text

def normalize_time(text):
    return text.replace(".", ":").strip()

def get_keyboard_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📅 Дата окончания", "⏰ Время начала")
    kb.add("⏱ Время окончания", "📝 Описание")
    kb.add("🔍 Проверить данные", "♻ Изменить всё")
    kb.add("✅ Отправить")
    return kb

# ===== Commands =====
@dp.message_handler(commands=["start"])
async def cmd_start(message: types.Message, state: FSMContext):
    user = get_user(message.chat.id)

    if not user:
        await Form.waiting_sheet.set()
        await message.answer(
            "👋 Привет!\n\n"
            "Я записываю события в твою Google Таблицу.\n\n"
            "📎 Пришли ссылку на таблицу, куда добавлять события.\n\n"
            "Таблица должна быть доступна на редактирование сервис-аккаунту."
        )
        return

    await message.answer(
        "▶ Нажми «Старт», чтобы добавить событие.",
        reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add("▶ Старт")
    )

# ===== Получение таблицы =====
@dp.message_handler(state=Form.waiting_sheet)
async def handle_sheet_link(message: types.Message, state: FSMContext):
    url = message.text.strip()
    sheet_id = extract_sheet_id(url)

    if not sheet_id:
        await message.answer("❌ Не удалось распознать ссылку. Пришли корректную ссылку Google Sheets.")
        return

    try:
        ss = gs_client.open_by_key(sheet_id)
        sheet = ss.worksheet(SHEET_NAME)

        ensure_headers(sheet)

        set_user(message.chat.id, {
            "sheet_url": url,
            "sheet_id": sheet_id
        })

        await state.finish()
        await message.answer("✅ Таблица подключена!")
        await message.answer(
            "▶ Нажми «Старт», чтобы добавить событие.",
            reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add("▶ Старт")
        )

    except Exception as e:
        logging.exception(e)
        await message.answer("❌ Не удалось открыть таблицу. Проверь доступ и имя листа.")

# ===== Start Form =====
@dp.message_handler(lambda m: m.text == "▶ Старт")
async def start_form(message: types.Message, state: FSMContext):
    await state.finish()
    await Form.waiting_title.set()
    await message.answer("✏ Введи название события:")

# ===== Steps =====
@dp.message_handler(state=Form.waiting_title)
async def step_title(message: types.Message, state: FSMContext):
    await state.update_data(title=message.text.strip())
    await Form.waiting_date_start.set()
    await message.answer("📅 Введи дату начала (ДД.ММ или ДД.ММ.ГГГГ):")

@dp.message_handler(state=Form.waiting_date_start)
async def step_date_start(message: types.Message, state: FSMContext):
    await state.update_data(date_start=normalize_date(message.text))
    await message.answer("Что хочешь добавить дальше?", reply_markup=get_keyboard_menu())

@dp.message_handler(lambda m: m.text == "📅 Дата окончания", state="*")
async def ask_date_end(message: types.Message):
    await Form.waiting_date_end.set()
    await message.answer("📅 Введи дату окончания:")

@dp.message_handler(lambda m: m.text == "⏰ Время начала", state="*")
async def ask_time_start(message: types.Message):
    await Form.waiting_time_start.set()
    await message.answer("⏰ Введи время начала (ЧЧ:ММ):")

@dp.message_handler(lambda m: m.text == "⏱ Время окончания", state="*")
async def ask_time_end(message: types.Message):
    await Form.waiting_time_end.set()
    await message.answer("⏱ Введи время окончания (ЧЧ:ММ):")

@dp.message_handler(lambda m: m.text == "📝 Описание", state="*")
async def ask_desc(message: types.Message):
    await Form.waiting_desc.set()
    await message.answer("📝 Введи описание:")

@dp.message_handler(state=Form.waiting_date_end)
async def step_date_end(message: types.Message, state: FSMContext):
    await state.update_data(date_end=normalize_date(message.text))
    await message.answer("Готово. Что дальше?", reply_markup=get_keyboard_menu())

@dp.message_handler(state=Form.waiting_time_start)
async def step_time_start(message: types.Message, state: FSMContext):
    await state.update_data(time_start=normalize_time(message.text))
    await message.answer("Готово. Что дальше?", reply_markup=get_keyboard_menu())

@dp.message_handler(state=Form.waiting_time_end)
async def step_time_end(message: types.Message, state: FSMContext):
    await state.update_data(time_end=normalize_time(message.text))
    await message.answer("Готово. Что дальше?", reply_markup=get_keyboard_menu())

@dp.message_handler(state=Form.waiting_desc)
async def step_desc(message: types.Message, state: FSMContext):
    await state.update_data(desc=message.text.strip())
    await message.answer("Готово. Что дальше?", reply_markup=get_keyboard_menu())

# ===== Review =====
@dp.message_handler(lambda m: m.text == "🔍 Проверить данные", state="*")
async def review(message: types.Message, state: FSMContext):
    data = await state.get_data()

    text = (
        f"📌 Название: {data.get('title','')}\n"
        f"📅 Дата начала: {data.get('date_start','')}\n"
        f"📅 Дата окончания: {data.get('date_end','')}\n"
        f"⏰ Время начала: {data.get('time_start','')}\n"
        f"⏱ Время окончания: {data.get('time_end','')}\n"
        f"📝 Описание: {data.get('desc','')}"
    )

    await message.answer(text)

@dp.message_handler(lambda m: m.text == "♻ Изменить всё", state="*")
async def reset_all(message: types.Message, state: FSMContext):
    await state.finish()
    await Form.waiting_title.set()
    await message.answer("✏ Введи название события заново:")

# ===== Send to Sheets =====
@dp.message_handler(lambda m: m.text == "✅ Отправить", state="*")
async def send_to_sheet(message: types.Message, state: FSMContext):
    data = await state.get_data()
    user = get_user(message.chat.id)

    try:
        ss = gs_client.open_by_key(user["sheet_id"])
        sheet = ss.worksheet(SHEET_NAME)

        row = [
            data.get("title",""),
            data.get("date_start",""),
            data.get("date_end",""),
            data.get("time_start",""),
            data.get("time_end",""),
            data.get("desc","")
        ]

        sheet.append_row(row, value_input_option="USER_ENTERED")

        await message.answer("✅ Событие добавлено в твою таблицу!")
        await state.finish()

    except Exception as e:
        logging.exception(e)
        await message.answer("❌ Ошибка при записи в таблицу.")

# ===== Run =====
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
