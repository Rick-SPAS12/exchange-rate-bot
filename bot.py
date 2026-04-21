import os
import requests
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor

API_TOKEN = os.getenv("API_TOKEN")

if not API_TOKEN:
    raise ValueError("API_TOKEN is missing")

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# ---------- НИЖНЯЯ КНОПКА ----------
keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
keyboard.add("📊 Exchange rates")

# ---------- INLINE КНОПКА ----------
inline_kb = InlineKeyboardMarkup().add(
    InlineKeyboardButton("🔄 Update", callback_data="update")
)

# ---------- ПОЛУЧЕНИЕ КУРСОВ ----------
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

# ---------- ТЕКСТ ----------
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

# ---------- /start ----------
@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    await message.answer("Press button 👇", reply_markup=keyboard)

# ---------- 📊 ----------
@dp.message_handler(lambda m: m.text == "📊 Exchange rates")
async def send_rates(message: types.Message):
    try:
        await message.answer(
            build_text(),
            reply_markup=inline_kb,
            parse_mode="HTML"
        )
    except:
        await message.answer("Error loading rates")

# ---------- 🔄 ----------
@dp.callback_query_handler(lambda c: c.data == "update")
async def update(callback: types.CallbackQuery):
    try:
        await callback.message.edit_text(
            build_text(),
            reply_markup=inline_kb,
            parse_mode="HTML"
        )
    except:
        pass

# ---------- ЗАПУСК ----------
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
