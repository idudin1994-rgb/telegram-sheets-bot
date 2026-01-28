import os
import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
)
from aiogram.filters import CommandStart
import gspread
from google.oauth2.service_account import Credentials

TOKEN = os.getenv("8257397371:AAFhMqkABmKhl0WwAe7-b7uuVoQf91dqUl0")
SPREADSHEET_ID = "1Xw6sLPUOV3GVAwLGBL7IdCq5CyH6v1qFO3z9IS8NhH0"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

creds = Credentials.from_service_account_file("credentials.json", scopes=SCOPES)
gc = gspread.authorize(creds)
ws = gc.open_by_key(SPREADSHEET_ID).sheet1

bot = Bot(token=TOKEN)
dp = Dispatcher()

users = {}

def new_event():
    return {
        "title": "",
        "date_start": "",
        "date_end": "",
        "time_start": "",
        "time_end": "",
        "desc": "",
        "row": None
    }

def get_user(uid):
    if uid not in users:
        users[uid] = {
            "mode": None,
            "step": None,
            "event": new_event(),
            "search": "",
            "found": []
        }
    return users[uid]

# ---------- КНОПКИ ----------

def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("➕ Добавить событие", callback_data="add")],
        [InlineKeyboardButton("✏️ Редактировать событие", callback_data="edit")],
        [InlineKeyboardButton("🗑 Удалить событие", callback_data="delete")]
    ])

def event_menu(e):
    kb = []

    row1 = []
    if not e["date_end"]:
        row1.append(InlineKeyboardButton("📅 Дата окончания", "date_end"))
    if not e["time_start"]:
        row1.append(InlineKeyboardButton("⏰ Время начала", "time_start"))
    if row1:
        kb.append(row1)

    row2 = []
    if not e["desc"]:
        row2.append(InlineKeyboardButton("📝 Описание", "desc"))
    if not e["time_end"]:
        row2.append(InlineKeyboardButton("⏱ Время окончания", "time_end"))
    if row2:
        kb.append(row2)

    kb.append([
        InlineKeyboardButton("🔍 Проверить данные", "check"),
        InlineKeyboardButton("♻ Изменить всё", "reset")
    ])

    kb.append([InlineKeyboardButton("✅ Отправить", "send")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

# ---------- GOOGLE SHEETS ----------

def ensure_headers():
    if ws.acell("A1").value is None:
        ws.append_row([
            "Название", "Дата начала", "Дата окончания",
            "Время начала", "Время окончания", "Описание"
        ])

def save_event(e):
    ensure_headers()
    ws.append_row([
        e["title"], e["date_start"], e["date_end"],
        e["time_start"], e["time_end"], e["desc"]
    ], value_input_option="USER_ENTERED")

def update_event(e):
    ws.update(f"A{e['row']}:F{e['row']}", [[
        e["title"], e["date_start"], e["date_end"],
        e["time_start"], e["time_end"], e["desc"]
    ]])

def delete_event(row):
    ws.delete_rows(row)

def search_events(query):
    rows = ws.get_all_values()[1:]
    result = []

    for i, r in enumerate(rows, start=2):
        title, ds = r[0], r[1]
        if query.lower() in title.lower() or query in ds:
            result.append((i, r))

    return result

# ---------- START ----------

@dp.message(CommandStart())
async def start(msg: Message):
    users.pop(msg.from_user.id, None)
    await msg.answer("Что нужно сделать?", reply_markup=main_menu())

# ---------- CALLBACK ----------

@dp.callback_query()
async def callbacks(call: CallbackQuery):
    user = get_user(call.from_user.id)
    e = user["event"]

    if call.data in ("add", "edit", "delete"):
        user["mode"] = call.data
        user["step"] = "search" if call.data != "add" else "title"
        user["event"] = new_event()

        text = (
            "✏️ Введи название события:"
            if call.data == "add"
            else "🔍 Введи данные для поиска события:"
        )
        await call.message.answer(text)
        await call.answer()
        return

    if call.data.startswith("pick_"):
        idx = int(call.data.split("_")[1])
        row, r = user["found"][idx]

        user["event"] = {
            "title": r[0],
            "date_start": r[1],
            "date_end": r[2],
            "time_start": r[3],
            "time_end": r[4],
            "desc": r[5],
            "row": row
        }

        if user["mode"] == "delete":
            await call.message.answer(
                f"❗ Удалить событие?\n\n📌 {r[0]}\n📅 {r[1]}",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton("❌ Отмена", "cancel"),
                        InlineKeyboardButton("🗑 Удалить", "confirm_delete")
                    ]
                ])
            )
        else:
            await call.message.answer(
                "Редактирование события:",
                reply_markup=event_menu(user["event"])
            )

        await call.answer()
        return

    if call.data == "confirm_delete":
        delete_event(user["event"]["row"])
        users.pop(call.from_user.id)
        await call.message.answer("🗑 Удалено", reply_markup=main_menu())
        await call.answer()
        return

    if call.data == "cancel":
        users.pop(call.from_user.id)
        await call.message.answer("Отменено", reply_markup=main_menu())
        await call.answer()
        return

    if call.data in ("date_end", "time_start", "time_end", "desc"):
        user["step"] = call.data
        await call.message.answer("Введи значение:")
        await call.answer()
        return

    if call.data == "reset":
        user["event"] = new_event()
        user["step"] = "title"
        await call.message.answer("✏️ Введи название:")
        await call.answer()
        return

    if call.data == "check":
        e = user["event"]
        await call.message.answer(
            f"📌 {e['title']}\n📅 {e['date_start']} – {e['date_end'] or '—'}\n"
            f"⏰ {e['time_start'] or '—'} – {e['time_end'] or '—'}\n"
            f"📝 {e['desc'] or '—'}",
            reply_markup=event_menu(e)
        )
        await call.answer()
        return

    if call.data == "send":
        if user["mode"] == "edit":
            update_event(user["event"])
        else:
            save_event(user["event"])

        users.pop(call.from_user.id)
        await call.message.answer("✅ Готово!", reply_markup=main_menu())
        await call.answer()

# ---------- TEXT ----------

@dp.message(F.text)
async def text_handler(msg: Message):
    user = get_user(msg.from_user.id)
    e = user["event"]

    if user["step"] == "search":
        found = search_events(msg.text)
        if not found:
            await msg.answer("❌ Ничего не найдено", reply_markup=main_menu())
            users.pop(msg.from_user.id)
            return

        user["found"] = found

        if len(found) == 1:
            row, r = found[0]
            user["event"] = {
                "title": r[0],
                "date_start": r[1],
                "date_end": r[2],
                "time_start": r[3],
                "time_end": r[4],
                "desc": r[5],
                "row": row
            }
            await msg.answer(
                "Событие найдено",
                reply_markup=event_menu(user["event"])
            )
        else:
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    f"{r[0]} — {r[1]}", f"pick_{i}"
                )] for i, (_, r) in enumerate(found)
            ])
            await msg.answer("Найдено несколько событий:", reply_markup=kb)

        return

    if user["step"] == "title":
        e["title"] = msg.text
        user["step"] = "date_start"
        await msg.answer("📅 Введи дату начала:")
        return

    if user["step"] == "date_start":
        e["date_start"] = msg.text
        user["step"] = None
        await msg.answer("Выбери действие:", reply_markup=event_menu(e))
        return

    if user["step"] in ("date_end", "time_start", "time_end", "desc"):
        e[user["step"]] = msg.text
        user["step"] = None
        await msg.answer("Готово", reply_markup=event_menu(e))

# ---------- RUN ----------

async def main():
    print("Bot started")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
