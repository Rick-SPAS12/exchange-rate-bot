import os
import asyncio
import requests

from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor

# ---------- TOKEN ----------
API_TOKEN = os.getenv("API_TOKEN") or "PASTE_YOUR_TOKEN_HERE"

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

CHANNEL_ID = "@bi11ionaire"

# ---------- CACHE ----------
cache = {}
prev_cache = {}

# ---------- UI ----------
inline_kb = InlineKeyboardMarkup().add(
    InlineKeyboardButton("🔄 Update", callback_data="update")
)

keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
keyboard.add("📊 Exchange", "🚀 TOP")

# ---------- REQUEST ----------
def safe_get(url, params=None):
    try:
        r = requests.get(url, params=params, timeout=10)
        if r.status_code == 200:
            return r.json()
    except:
        pass
    return None

# ---------- P2P ----------
def get_p2p_price(fiat):
    try:
        r = requests.post(
            "https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search",
            json={
                "asset": "USDT",
                "fiat": fiat,
                "page": 1,
                "rows": 1,
                "tradeType": "BUY"
            },
            timeout=10
        ).json()

        if isinstance(r, dict) and r.get("data"):
            return float(r["data"][0]["adv"]["price"])
    except:
        pass

    return None

# ---------- MARKET ----------
def fetch_rates():
    crypto = safe_get(
        "https://api.coingecko.com/api/v3/simple/price",
        params={
            "ids": "bitcoin,ethereum,the-open-network",
            "vs_currencies": "usd"
        }
    )

    if not crypto:
        return None

    return {
        "btc": float(crypto["bitcoin"]["usd"]),
        "eth": float(crypto["ethereum"]["usd"]),
        "ton": float(crypto["the-open-network"]["usd"]),
        "rub": get_p2p_price("RUB") or cache.get("rub", 90),
        "cny": get_p2p_price("CNY") or cache.get("cny", 7.2),
    }

# ---------- TOP ----------
def get_top():
    try:
        r = safe_get(
            "https://api.coingecko.com/api/v3/coins/markets",
            params={
                "vs_currency": "usd",
                "order": "market_cap_desc",
                "per_page": 50,
                "page": 1,
                "price_change_percentage": "1h"
            }
        )

        if not isinstance(r, list):
            return []

        movers = []
        for c in r:
            ch = c.get("price_change_percentage_1h_in_currency")
            if ch is None:
                continue

            movers.append((c["symbol"].upper(), float(ch)))

        movers.sort(key=lambda x: abs(x[1]), reverse=True)
        return movers[:5]

    except:
        return []

# ---------- FORMAT ----------
def pct(new, old):
    if not old:
        return 0
    return ((new - old) / old) * 100

def format_price(name, value):
    if name in ["BTC", "ETH"]:
        return f"{value:,.0f}"
    elif name == "TON":
        return f"{value:.2f}"
    return f"{value:.2f}"

def line(sym, name, value, old, suffix=""):
    price = format_price(name, value)

    if not old:
        return f"{sym} {name}: {price}{suffix}"

    ch = pct(value, old)

    if value > old:
        return f"{sym} {name}: {price}{suffix} (+{ch:.2f}%) 🟢"
    elif value < old:
        return f"{sym} {name}: {price}{suffix} ({ch:.2f}%) 🔴"

    return f"{sym} {name}: {price}{suffix}"

# ---------- TEXT ----------
def build_text():
    if not cache:
        return "📊 Loading..."

    p = prev_cache or cache

    return (
        "<b>📊 LIVE MARKET</b>\n\n"
        f"{line('₿','BTC',cache['btc'],p.get('btc'))}\n"
        f"{line('Ξ','ETH',cache['eth'],p.get('eth'))}\n"
        f"{line('▽','TON',cache['ton'],p.get('ton'))}\n\n"
        f"{line('','USD→RUB',cache['rub'],p.get('rub'), ' ₽')}\n"
        f"{line('','USD→CNY',cache['cny'],p.get('cny'), ' ¥')}\n\n"
        "📌 <a href='https://t.me/send?start=r-x4zoa'>@CryptoBot</a>"
    )

# ---------- TOP TEXT ----------
def build_top():
    data = get_top()

    if not data:
        return "🚀 TOP MOVERS\n\nНет данных"

    text = "🚀 TOP MOVERS (1h)\n\n"

    for sym, ch in data:
        icon = "🟢" if ch > 0 else "🔴"
        sign = "+" if ch > 0 else ""
        text += f"{sym} {sign}{ch:.2f}% {icon}\n"

    text += "\n📌 @bi11ionaire"
    return text

# ---------- LOOP ----------
async def updater():
    global cache, prev_cache

    while True:
        data = fetch_rates()
        if data:
            prev_cache = cache.copy() if cache else data
            cache = data

        await asyncio.sleep(300)

async def market_poster():
    last = ""

    while True:
        if cache:
            text = build_text()

            if text != last:
                await bot.send_message(
                    CHANNEL_ID,
                    text,
                    parse_mode="HTML",
                    disable_web_page_preview=True
                )
                last = text

        await asyncio.sleep(300)

async def top_poster():
    last = ""

    while True:
        text = build_top()

        if text != last:
            await bot.send_message(
                CHANNEL_ID,
                text,
                disable_web_page_preview=True
            )
            last = text

        await asyncio.sleep(3600)

# ---------- HANDLERS ----------
@dp.message_handler(commands=["start"])
async def start(m: types.Message):
    await m.answer("Choose:", reply_markup=keyboard)

@dp.message_handler(lambda m: m.text and "Exchange" in m.text)
async def rates(m: types.Message):
    await m.answer(
        build_text(),
        parse_mode="HTML",
        reply_markup=inline_kb,
        disable_web_page_preview=True
    )

@dp.message_handler(lambda m: m.text and "TOP" in m.text)
async def top(m: types.Message):
    await m.answer(
        build_top(),
        disable_web_page_preview=True
    )

@dp.callback_query_handler(lambda c: c.data == "update")
async def update(c: types.CallbackQuery):
    await c.answer()
    await c.message.edit_text(
        build_text(),
        parse_mode="HTML",
        reply_markup=inline_kb,
        disable_web_page_preview=True
    )

# ---------- START ----------
async def on_startup(_):
    asyncio.create_task(updater())
    asyncio.create_task(market_poster())
    asyncio.create_task(top_poster())

# ---------- RUN ----------
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
