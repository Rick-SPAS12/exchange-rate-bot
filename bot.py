import os
import asyncio
import requests

from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor

API_TOKEN = os.getenv("API_TOKEN")

if not API_TOKEN:
    raise ValueError("API_TOKEN is missing")

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# 👉 твой канал
CHANNEL_ID = "@your_channel"

# ---------- STATE ----------
live_tasks = {}

# ---------- KEYBOARDS ----------
inline_kb = InlineKeyboardMarkup(row_width=2)
inline_kb.add(
    InlineKeyboardButton("🔄 Update", callback_data="update"),
    InlineKeyboardButton("📡 Live ON", callback_data="live_on")
)

live_kb = InlineKeyboardMarkup(row_width=2)
live_kb.add(
    InlineKeyboardButton("🔄 Update", callback_data="update"),
    InlineKeyboardButton("⛔ Stop Live", callback_data="live_off")
)

keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
keyboard.add("📊 Exchange rates")

# ---------- API ----------
def get_rates():
    crypto = requests.get(
        "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,the-open-network&vs_currencies=usd"
    ).json()

    fx = requests.get(
        "https://api.exchangerate-api.com/v4/latest/USD"
    ).json()["rates"]

    return (
        crypto["bitcoin"]["usd"],
        crypto["ethereum"]["usd"],
        crypto["the-open-network"]["usd"],
        fx["RUB"],
        fx["CNY"],
    )

# ---------- TEXT ----------
def build_text():
    btc, eth, ton, rub, cny = get_rates()

    return (
        "📊 Rates (LIVE)\n\n"
        f"₿ BTC: ${btc:,.2f}\n"
        f"Ξ ETH: ${eth:,.2f}\n"
        f"💎 TON: ${ton:,.2f}\n"
        f"💵 USD → RUB: {rub:,.2f} ₽\n"
        f"🇨🇳 USD → CNY: {cny:,.2f} ¥\n\n"
        '📌 <a href="https://t.me/send?start=r-x4zoa">@CryptoBot</a>'
    )

# ---------- LIVE LOOP ----------
async def live_update(chat_id, message_id):
    while True:
        try:
            await bot.edit_message_text(
                build_text(),
                chat_id=chat_id,
                message_id=message_id,
                reply_markup=live_kb,
                parse_mode="HTML"
            )
        except:
            break

        await asyncio.sleep(10)

# ---------- CHANNEL POSTER ----------
async def channel_poster():
    while True:
        try:
            await bot.send_message(
                CHANNEL_ID,
                build_text(),
                parse_mode="HTML"
            )
        except:
            pass

        await asyncio.sleep(300)  # 5 минут

# ---------- START ----------
@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    await message.answer("Press button 👇", reply_markup=keyboard)

# ---------- RATES ----------
@dp.message_handler(lambda m: m.text == "📊 Exchange rates")
async def send_rates(message: types.Message):
    await message.answer(
        build_text(),
        reply_markup=inline_kb,
        parse_mode="HTML"
    )

# ---------- UPDATE ----------
@dp.callback_query_handler(lambda c: c.data == "update")
async def update(callback: types.CallbackQuery):
    await callback.answer("🔄 Updated")

    await callback.message.edit_text(
        build_text(),
        reply_markup=inline_kb,
        parse_mode="HTML"
    )

# ---------- LIVE ON ----------
@dp.callback_query_handler(lambda c: c.data == "live_on")
async def live_on(callback: types.CallbackQuery):
    await callback.answer("📡 Live started")

    task = asyncio.create_task(
        live_update(callback.message.chat.id, callback.message.message_id)
    )

    live_tasks[callback.message.message_id] = task

# ---------- LIVE OFF ----------
@dp.callback_query_handler(lambda c: c.data == "live_off")
async def live_off(callback: types.CallbackQuery):
    await callback.answer("⛔ Live stopped")

    task = live_tasks.get(callback.message.message_id)
    if task:
        task.cancel()
        del live_tasks[callback.message.message_id]

# ---------- RUN ----------
if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(channel_poster())

    executor.start_polling(dp, skip_updates=True)
