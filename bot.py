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
cache = None
prev_cache = None

# ---------- KEYBOARD ----------
inline_kb = InlineKeyboardMarkup().add(
    InlineKeyboardButton("🔄 Update", callback_data="update")
)

keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
keyboard.add("📊 Exchange rates")

# ---------- SAFE GET ----------
def safe_get(url, params=None):
    try:
        r = requests.get(url, params=params, timeout=8)
        return r.json()
    except:
        return None

# ---------- SAFE P2P ----------
def get_p2p_price(fiat):
    try:
        url = "https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search"

        payload = {
            "asset": "USDT",
            "fiat": fiat,
            "merchantCheck": False,
            "page": 1,
            "rows": 1,
            "tradeType": "BUY"
        }

        r = requests.post(url, json=payload, timeout=8)

        data = r.json()
        if not data or "data" not in data or len(data["data"]) == 0:
            return None

        return float(data["data"][0]["adv"]["price"])

    except:
        return None

# ---------- FETCH (ROBUST) ----------
def fetch_rates():
    crypto = safe_get(
        "https://api.coingecko.com/api/v3/simple/price",
        params={
            "ids": "bitcoin,ethereum,the-open-network",
            "vs_currencies": "usd"
        }
    )

    # ❗ если CoinGecko умер — НЕ ломаем бот
    if not crypto:
        return cache

    rub = get_p2p_price("RUB")
    cny = get_p2p_price("CNY")

    # fallback всегда работает
    if cache:
        rub = rub or cache["rub"]
        cny = cny or cache["cny"]
    else:
        rub = rub or 90
        cny = cny or 7.2

    return {
        "btc": float(crypto["bitcoin"]["usd"]),
        "eth": float(crypto["ethereum"]["usd"]),
        "ton": float(crypto["the-open-network"]["usd"]),
        "rub": rub,
        "cny": cny,
    }

# ---------- LIVE UPDATE ----------
async def live_updater():
    global cache, prev_cache

    while True:
        try:
            data = fetch_rates()

            if data:
                prev_cache = cache.copy() if cache else data
                cache = data

        except:
            pass

        await asyncio.sleep(150)

# ---------- % ----------
def pct(new, old):
    if not old:
        return 0
    return ((new - old) / old) * 100

# ---------- FORMAT ----------
def format_line(name, value, old, suffix=""):
    if not old:
        return f"{name}: {value:.2f}{suffix} ⚪ (0.00%)"

    change = pct(value, old)

    if abs(change) < 0.01:
        icon = "⚪"
        sign = ""
    elif change > 0:
        icon = "🟢"
        sign = "+"
    else:
        icon = "🔴"
        sign = ""

    return f"{name}: {value:.2f}{suffix} ({sign}{change:.2f}%) {icon}"

# ---------- TEXT ----------
def build_text():
    if not cache:
        return "📊 Market initializing..."

    return (
        "📊 LIVE MARKET\n\n"
        f"₿ {format_line('BTC', cache['btc'], prev_cache['btc'] if prev_cache else 0)}\n"
        f"Ξ {format_line('ETH', cache['eth'], prev_cache['eth'] if prev_cache else 0)}\n"
        f"▽{format_line('TON', cache['ton'], prev_cache['ton'] if prev_cache else 0)}\n\n"
        f"💵 {format_line('USD→RUB', cache['rub'], prev_cache['rub'] if prev_cache else 0, ' ₽')}\n"
        f"🇨🇳 {format_line('USD→CNY', cache['cny'], prev_cache['cny'] if prev_cache else 0, ' ¥')}\n\n"
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

# ---------- CHANNEL ----------
async def channel_poster():
    last_sent = ""

    while True:
        try:
            text = build_text()

            if cache and text != last_sent:
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

    # init fallback (ВАЖНО)
    data = fetch_rates()
    if data:
        cache = data
        prev_cache = data.copy()

    asyncio.create_task(live_updater())
    asyncio.create_task(channel_poster())

# ---------- RUN ----------
if __name__ == "__main__":
    executor.start_polling(
        dp,
        skip_updates=True,
        on_startup=on_startup
    )
