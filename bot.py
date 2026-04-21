import os
import asyncio
import requests

from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor

# ---------- TOKEN ----------
API_TOKEN = os.getenv("API_TOKEN")

if not API_TOKEN:
    raise ValueError("API_TOKEN is missing")

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# ---------- CHANNEL ----------
CHANNEL_ID = "@bi11ionaire"  # <-- твой канал

# ---------- KEYBOARD ----------
inline_kb = InlineKeyboardMarkup()
inline_kb.add(
    InlineKeyboardButton("🔄 Update", callback_data="update")
)

keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
keyboard.add("📊 Exchange rates")

# ---------- API ----------
def get_rates():
    crypto = requests.get(
        "https://api.coingecko.com/api/v3/simple/price",
        params={
            "ids": "bitcoin,ethereum,the-open-network",
            "vs_currencies": "usd"
        },
        timeout=10
    ).json()

    fx = requests.get(
        "https://open.er-api.com/v6/latest/USD",
        timeout=10
    ).json().get("rates", {})

    return (
        crypto["bitcoin"]["usd"],
        crypto["ethereum"]["usd"],
        crypto["the-open-network"]["usd"],
        fx.get("RUB", 0),
        fx.get("CNY", 0),
    )

# ---------- TEXT ----------
def build_text():
    btc, eth, ton, rub, cny = get_rates()

    return (
        "📊 Rates\n\n"
        f"₿ BTC: ${btc:,.2f}\n"
        f"Ξ ETH: ${eth:,.2f}\n"
        f"💎 TON: ${ton:,.2f}\n"
        f"💵 USD → RUB: {rub:,.2f} ₽\n"
        f"🇨🇳 USD → CNY: {cny:,.2f} ¥\n\n"
        '📌 <a href="https://t.me/CryptoBot">"@CryptoBot</a>'
    )

# ---------- HANDLERS ----------
@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    await message.answer("Choose option 👇", reply_markup=keyboard)

@dp.message_handler(lambda m: m.text == "📊 Exchange rates")
async def rates(message: types.Message):
    await message.answer(
        build_text(),
        reply_markup=inline_kb,
        parse_mode="HTML",
        disable_web_page_preview=True
    )

@dp.callback_query_handler(lambda c: c.data == "update")
async def update(callback: types.CallbackQuery):
    await callback.answer("🔄 Updated")

    await callback.message.edit_text(
        build_text(),
        reply_markup=inline_kb,
        parse_mode="HTML",
        disable_web_page_preview=True
    )

# ---------- CHANNEL POST ----------
async def channel_poster():
    while True:
        try:
            await bot.send_message(
                CHANNEL_ID,
                build_text(),
                parse_mode="HTML",
                disable_web_page_preview=True
            )
        except:
            pass

        await asyncio.sleep(300)

# ---------- STARTUP ----------
async def on_startup(_):
    asyncio.create_task(channel_poster())

# ---------- RUN ----------
if __name__ == "__main__":
    executor.start_polling(
        dp,
        skip_updates=True,
        on_startup=on_startup
    )
