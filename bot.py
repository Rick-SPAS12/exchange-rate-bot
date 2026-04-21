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

CHANNEL_ID = "@your_channel"

# ---------- CACHE ----------
cache = {
    "btc": 0,
    "eth": 0,
    "ton": 0,
    "rub": 0,
    "cny": 0
}

# ---------- KEYBOARD ----------
inline_kb = InlineKeyboardMarkup(row_width=2)
inline_kb.add(
    InlineKeyboardButton("🔄 Update", callback_data="update")
)

keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
keyboard.add("📊 Exchange rates")

# ---------- FAST FETCH ----------
def fetch_rates():
    crypto = requests.get(
        "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,the-open-network&vs_currencies=usd",
        timeout=10
    ).json()

    fx = requests.get(
        "https://api.exchangerate-api.com/v4/latest/USD",
        timeout=10
    ).json()["rates"]

    return (
        crypto["bitcoin"]["usd"],
        crypto["ethereum"]["usd"],
        crypto["the-open-network"]["usd"],
        fx["RUB"],
        fx["CNY"],
    )

# ---------- CACHE UPDATER (FAST CORE) ----------
async def cache_updater():
    global cache

    while True:
        try:
            btc, eth, ton, rub, cny = fetch_rates()

            cache["btc"] = btc
            cache["eth"] = eth
            cache["ton"] = ton
            cache["rub"] = rub
            cache["cny"] = cny

        except:
            pass

        await asyncio.sleep(15)  # обновление кеша

# ---------- TEXT ----------
def build_text():
    return (
        "📊 Rates (ULTRA FAST)\n\n"
        f"₿ BTC: ${cache['btc']:,.2f}\n"
        f"Ξ ETH: ${cache['eth']:,.2f}\n"
        f"💎 TON: ${cache['ton']:,.2f}\n"
        f"💵 USD → RUB: {cache['rub']:,.2f} ₽\n"
        f"🇨🇳 USD → CNY: {cache['cny']:,.2f} ¥\n\n"
        '📌 <a href="https://t.me/send?start=r-x4zoa">@CryptoBot</a>'
    )

# ---------- HANDLERS ----------
@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    await message.answer("Press button 👇", reply_markup=keyboard)

@dp.message_handler(lambda m: m.text == "📊 Exchange rates")
async def rates(message: types.Message):
    await message.answer(
        build_text(),
        reply_markup=inline_kb,
        parse_mode="HTML"
    )

@dp.callback_query_handler(lambda c: c.data == "update")
async def update(callback: types.CallbackQuery):
    await callback.answer("🔄 Updated")

    await callback.message.edit_text(
        build_text(),
        reply_markup=inline_kb,
        parse_mode="HTML"
    )

# ---------- CHANNEL POST ----------
async def channel_poster():
    while True:
        await bot.send_message(
            CHANNEL_ID,
            build_text(),
            parse_mode="HTML"
        )
        await asyncio.sleep(300)

# ---------- START ----------
if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(cache_updater())     # 🔥 FAST CACHE
    loop.create_task(channel_poster())    # 📡 CHANNEL POST

    executor.start_polling(dp, skip_updates=True)
