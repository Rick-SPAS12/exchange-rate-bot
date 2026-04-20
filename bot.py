import asyncio
import requests

from aiogram import Bot, Dispatcher
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton

import os

API_TOKEN = os.getenv("API_TOKEN")

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# ---------- КНОПКИ ----------
keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📊 Exchange rates.")]
    ],
    resize_keyboard=True
)

# ---------- ПОЛУЧЕНИЕ КУРСОВ ----------
def get_rates():
    crypto_url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,the-open-network&vs_currencies=usd"
    crypto = requests.get(crypto_url).json()

    btc = crypto["bitcoin"]["usd"]
    eth = crypto["ethereum"]["usd"]
    ton = crypto["the-open-network"]["usd"]

    fx = requests.get("https://api.exchangerate-api.com/v4/latest/USD").json()["rates"]

    rub = fx["RUB"]
    cny = fx["CNY"]

    return btc, eth, ton, rub, cny

# ---------- ХЕНДЛЕР ----------
@dp.message()
async def handler(message: Message):

    # старт
    if message.text == "/start":
        await message.answer("choose an action:", reply_markup=keyboard)
        return

    # кнопка курс
    if message.text == "📊 Exchange rates.":
        try:
            btc, eth, ton, rub, cny = get_rates()

            text = (
                "📊 currencies:\n\n"
                f"₿ BTC: ${btc}\n"
                f"Ξ ETH: ${eth}\n"
                f"💎 TON: ${ton}\n"
                f"💵 USD → RUB: {rub} ₽\n"
                f"🇨🇳 USD → CNY: {cny} ¥"
            )

            await message.answer(text)

        except Exception:
            await message.answer("Ошибка получения курсов 😢")

# ---------- ЗАПУСК ----------
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
