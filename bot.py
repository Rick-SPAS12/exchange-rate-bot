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
cache = {}
prev_cache = {}

# ---------- KEYBOARD ----------
inline_kb = InlineKeyboardMarkup().add(
    InlineKeyboardButton("🔄 Update", callback_data="update")
)

keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
keyboard.add("📊 Exchange rates")

# ---------- SAFE REQUEST ----------
def safe_get(url, timeout=10):
    try:
        r = requests.get(url, timeout=timeout)
        if r.status_code == 200:
            return r.json()
    except:
        pass
    return None

# ---------- FETCH (WITH FALLBACK) ----------
def fetch_rates():
    crypto = safe_get(
        "https://api.coingecko.com/api/v3/simple/price",
        timeout=10
    )

    if crypto:
        crypto = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={
                "ids": "bitcoin,ethereum,the-open-network",
                "vs_currencies": "usd"
            },
            timeout=10
        ).json()

    fx = safe_get("https://open.er-api.com/v6/latest/USD")

    if not crypto or not fx:
        return None

    rates = fx.get("rates", {})

    try:
        return {
            "btc": float(crypto["bitcoin"]["usd"]),
            "eth": float(crypto["ethereum"]["usd"]),
            "ton": float(crypto["the-open-network"]["usd"]),
            "rub": float(rates.get("RUB", 0)),
            "cny": float(rates.get("CNY", 0)),
        }
    except:
        return None

# ---------- LIVE UPDATE ----------
async def live_updater():
    global cache, prev_cache

    while True:
        data = fetch_rates()

        if data:
            prev_cache = cache.copy() if cache else data.copy()
            cache = data

        await asyncio.sleep(60)

# ---------- % CHANGE ----------
def percent_change(new, old):
    if not old or old == 0:
        return 0
    return ((new - old) / old) * 100

def format_line(name, value, old):
    if not old:
        return f"{name}: ${value:,.2f}"

    change = percent_change(value, old)
    arrow = "🟢" if change >= 0 else "🔴"

    return f"{name}: ${value:,.2f} ({change:+.2f}%) {arrow}"

# ---------- TEXT ----------
def build_text():
    if not cache:
        return "⏳ Loading market data..."

    return (
        "📊 LIVE MARKET\n\n"
        f"₿ {format_line('BTC', cache.get('btc', 0), prev_cache.get('btc', 0))}\n"
        f"Ξ {format_line('ETH', cache.get('eth', 0), prev_cache.get('eth', 0))}\n"
        f"💎 {format_line('TON', cache.get('ton', 0), prev_cache.get('ton', 0))}\n"
        f"💵 USD → RUB: {cache.get('rub', 0):,.2f} ₽\n"
        f"🇨🇳 USD → CNY: {cache.get('cny', 0):,.2f} ¥\n\n"
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
    await callback.answer()

    await callback.message.edit_text(
        build_text(),
        reply_markup=inline_kb,
        parse_mode="HTML",
        disable_web_page_preview=True
    )

# ---------- CHANNEL POST ----------
async def channel_poster():
    last_sent = ""

    while True:
        text = build_text()

        if text != last_sent and "Loading" not in text:
            try:
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
    global cache, prev_cache

    # 🔥 initial load with retries
    for _ in range(5):
        data = fetch_rates()
        if data:
            cache = data
            prev_cache = data.copy()
            break
        await asyncio.sleep(2)

    asyncio.create_task(live_updater())
    asyncio.create_task(channel_poster())

# ---------- RUN ----------
if __name__ == "__main__":
    executor.start_polling(
        dp,
        skip_updates=True,
        on_startup=on_startup
    )
