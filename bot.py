import os
import requests
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor

API_TOKEN = os.getenv("API_TOKEN")

if not API_TOKEN:
    raise ValueError("API_TOKEN is missing")

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
keyboard.add("📊 Exchange rates")

def get_rates():
    crypto = requests.get(
        "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,the-open-network&vs_currencies=usd"
    ).json()

    fx = requests.get("https://api.exchangerate-api.com/v4/latest/USD").json()["rates"]

    return (
        crypto["bitcoin"]["usd"],
        crypto["ethereum"]["usd"],
        crypto["the-open-network"]["usd"],
        fx["RUB"],
        fx["CNY"],
    )

@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    await message.answer("Choose action:", reply_markup=keyboard)

@dp.message_handler(lambda m: m.text == "📊 Exchange rates")
async def rates(message: types.Message):
    try:
        btc, eth, ton, rub, cny = get_rates()

        await message.answer(
            "📊 Rates:\n\n"
    f"₿ BTC: ${btc:,.2f}\n"
    f"Ξ ETH: ${eth:,.2f}\n"
    f"💎 TON: ${ton:,.2f}\n"
    f"💵 USD → RUB: {rub:,.2f} ₽\n"
    f"🇨🇳 USD → CNY: {cny:,.2f} ¥"
       "💡https://t.me/send?start=r-x4zoa" )
    except:
        await message.answer("Error loading rates")

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
