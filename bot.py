import os
import time
import requests
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor

API_TOKEN = os.getenv("API_TOKEN")

if not API_TOKEN:
    raise ValueError("API_TOKEN is missing")

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# ---------- anti-spam ----------
last_update = {}

# ---------- inline button ----------
inline_kb = InlineKeyboardMarkup().add(
    InlineKeyboardButton("🔄 Update", callback_data="update")
)

# ---------- bottom button ----------
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

# ---------- text ----------
def build_text():
    btc, eth, ton, rub, cny = get_rates()

    return (
        "📊 Rates:\n\n"
        f"₿ BTC: ${btc:,.2f}\n"
        f"Ξ ETH: ${eth:,.2f}\n"
        f"💎 TON: ${ton:,.2f}\n"
        f"💵 USD → RUB: {rub:,.2f} ₽\n"
        f"🇨🇳 USD → CNY: {cny:,.2f} ¥\n\n"
        '📌 <a href="https://t.me/send?start=r-x4zoa">@CryptoBot</a>'
    )

# ---------- start ----------
@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    await message.answer("Press a button below 👇", reply_markup=keyboard)

# ---------- rates ----------
@dp.message_handler(lambda m: m.text == "📊 Exchange rates")
async def send_rates(message: types.Message):
    try:
        await message.answer(
            build_text(),
            reply_markup=inline_kb,
            parse_mode="HTML"
        )
    except:
        await message.answer("Error loading rates ❌")

# ---------- update ----------
@dp.callback_query_handler(lambda c: c.data == "update")
async def update(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    now = time.time()

    # anti-spam
    if user_id in last_update and now - last_update[user_id] < 3:
        await callback.answer("⏳ Too fast")
        return

    last_update[user_id] = now

    # remove loading animation
    await callback.answer("🔄 Updating...")

    try:
        await callback.message.edit_text(
            build_text(),
            reply_markup=inline_kb,
            parse_mode="HTML"
        )
    except:
        await callback.answer("Update error ❌", show_alert=True)

# ---------- run ----------
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
