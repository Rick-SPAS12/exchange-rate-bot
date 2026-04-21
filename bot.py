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
CHANNEL_ID = "@bi11ionaire"

# ---------- CACHE ----------
cache = {
    "btc": 0.0,
    "eth": 0.0,
    "ton": 0.0,
    "rub": 0.0,
    "cny": 0.0
}

prev_cache = cache.copy()

# ---------- KEYBOARD ----------
inline_kb = InlineKeyboardMarkup().add(
    InlineKeyboardButton("🔄 Update", callback_data="update")
)

keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
keyboard.add("📊 Exchange rates")

# ---------- FETCH ----------
def fetch_rates():
    try:
        crypto = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={
                "ids": "bitcoin,ethereum,the-open-network",
                "vs_currencies": "usd"
            },
            timeout=10
        ).json()

        fx = requests.get(
            "https://api.exchangerate.host/latest",
            params={"base": "USD"},
            timeout=10
        ).json()

        if not fx.get("success", True):
            return None

        rates = fx.get("rates")
        if not rates:
            return None

        return {
            "btc": crypto["bitcoin"]["usd"],
            "eth": crypto["ethereum"]["usd"],
            "ton": crypto["the-open-network"]["usd"],
            "rub": float(rates.get("RUB", 0)),
            "cny": float(rates.get("CNY", 0)),
        }

    except:
        return None

# ---------- LIVE UPDATE ----------
async def live_updater():
    global cache, prev_cache

    while True:
        try:
            data = fetch_rates()
            if data:
                prev_cache = cache.copy()
                cache = data
        except:
            pass

        await asyncio.sleep(90)

# ---------- % CHANGE ----------
def percent_change(new, old):
    if old == 0:
        return 0
    return ((new - old) / old) * 100

def format_line(name, value, old):
    change = percent_change(value, old)
    arrow = "🟢" if change >= 0 else "🔴"
    return f"{name}: ${value:,.2f} ({change:+.2f}%) {arrow}"

# ---------- TEXT ----------
def build_text():
    if cache["btc"] == 0:
        return "⏳ Loading market data..."

    return (
        "📊 LIVE MARKET (5m)\n\n"
        f"₿ {format_line('BTC', cache['btc'], prev_cache['btc'])}\n"
        f"Ξ {format_line('ETH', cache['eth'], prev_cache['eth'])}\n"
        f"💎 {format_line('TON', cache['ton'], prev_cache['ton'])}\n"
        f"💵 USD → RUB: {cache['rub']:,.2f} ₽\n"
        f"🇨🇳 USD → CNY: {cache['cny']:,.2f} ¥\n\n"
        '📌 <a href="https://t.me/send?start=r-x4zoa">@CryptoBot</a>'
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
    last_sent = None

    while True:
        try:
            text = build_text()

            # не постим если ещё грузится
            if "Loading" in text:
                await asyncio.sleep(10)
                continue

            if text != last_sent:
                await bot.send_message(
                    CHANNEL_ID,
                    text,
                    parse_mode="HTML",
                    disable_web_page_preview=True
                )
                last_sent = text

        except:
            pass

        await asyncio.sleep(300)

# ---------- STARTUP ----------
async def on_startup(_):
    global cache

    # 🔥 первичная загрузка
    data = fetch_rates()
    if data:
        cache = data

    asyncio.create_task(live_updater())
    asyncio.create_task(channel_poster())

# ---------- RUN ----------
if __name__ == "__main__":
    executor.start_polling(
        dp,
        skip_updates=True,
        on_startup=on_startup
    )
