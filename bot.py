import asyncio
import os
import requests

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton

# ---------- TOKEN ----------
API_TOKEN = os.getenv("API_TOKEN")

if not API_TOKEN:
    raise ValueError("API_TOKEN is not set in environment variables")

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# ---------- KEYBOARD ----------
keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📊 Exchange rates")]
    ],
    resize_keyboard=True
)

# ---------- RATES ----------
def get_rates():
    crypto_url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,the-open-network&vs_currencies=usd"
    crypto = requests.get(crypto_url, timeout=10).json()

    fx = requests.get("https://api.exchangerate-api.com/v4/latest/USD", timeout=10).json()["rates"]

    return (
        crypto["bitcoin"]["usd"],
        crypto["ethereum"]["usd"],
        crypto["the-open-network"]["usd"],
        fx["RUB"],
        fx["CNY"],
    )

# ---------- HANDLER ----------
@dp.message(F.text == "/start")
async def start(message: Message):
    await message.answer("Choose action:", reply_markup=keyboard)


@dp.message(F.text == "📊 Exchange rates")
async def rates(message: Message):
    try:
        btc, eth, ton, rub, cny = get_rates()

        await message.answer(
            "📊 Rates:\n\n"
            f"₿ BTC: ${btc}\n"
            f"Ξ ETH: ${eth}\n"
            f"💎 TON: ${ton}\n"
            f"💵 USD→RUB: {rub}\n"
            f"🇨🇳 USD→CNY: {cny}"
        )

    except Exception:
        await message.answer("Error getting rates")

# ---------- START ----------
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
