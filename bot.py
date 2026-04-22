import os
import asyncio
import requests

from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor

# ---------- TOKEN ----------
API_TOKEN = os.getenv("API_TOKEN") or "PASTE_YOUR_TOKEN_HERE"

if not API_TOKEN:
    raise ValueError("API_TOKEN is missing")

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# ---------- CHANNEL ----------
CHANNEL_ID = "@bi11ionaire"

# ---------- CACHE ----------
cache = {}
prev_cache = {}

# ---------- UI ----------
inline_kb = InlineKeyboardMarkup().add(
    InlineKeyboardButton("🔄 Update", callback_data="update")
)

keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
keyboard.add("📊 Exchange rates")

# ---------- SAFE GET ----------
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

    btc = crypto.get("bitcoin", {}).get("usd")
    eth = crypto.get("ethereum", {}).get("usd")
    ton = crypto.get("the-open-network", {}).get("usd")

    if None in (btc, eth, ton):
        return None

    rub = get_p2p_price("RUB")
    cny = get_p2p_price("CNY")

    return {
        "btc": float(btc),
        "eth": float(eth),
        "ton": float(ton),
        "rub": float(rub or cache.get("rub", 90) or 90),
        "cny": float(cny or cache.get("cny", 7.2) or 7.2),
    }

# ---------- MOVERS ----------
def get_top_movers():
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
            change = c.get("price_change_percentage_1h_in_currency")

            if change is None:
                continue

            movers.append({
                "symbol": c.get("symbol", "").upper(),
                "change": float(change)
            })

        movers.sort(key=lambda x: abs(x["change"]), reverse=True)
        return movers[:5]

    except:
        return []

# ---------- MARKET LOOP ----------
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

        await asyncio.sleep(300)

# ---------- MOVERS LOOP ----------
async def movers_poster():
    last = ""

    while True:
        try:
            movers = get_top_movers()

            if not movers:
                await asyncio.sleep(60)
                continue

            text = "🚀 TOP MOVERS (1h)\n\n"

            for m in movers:
                change = m["change"]

                if change > 0:
                    icon = "🟢"
                    sign = "+"
                else:
                    icon = "🔴"
                    sign = ""

                text += f"{m['symbol']} {sign}{change:.2f}% {icon}\n"

            if text != last:
                await bot.send_message(CHANNEL_ID, text)
                last = text

        except:
            pass

        await asyncio.sleep(3600)

# ---------- FORMAT ----------
def pct(new, old):
    if not old:
        return 0
    return ((new - old) / old) * 100

def format_price(name, value):
    if name == "TON":
        return f"{value:.2f}"
    elif name in ["BTC", "ETH"]:
        return f"{value:,.0f}"
    return f"{value:.2f}"

def format_line(name, value, old, suffix=""):
    price = format_price(name, value)

    if not old:
        return f"{name}: {price}{suffix}"

    change = pct(value, old)

    if value == old:
        return f"{name}: {price}{suffix}"

    if value > old:
        return f"{name}: {price}{suffix} (+{change:.2f}%) 🟢"

    return f"{name}: {price}{suffix} ({change:.2f}%) 🔴"

# ---------- TEXT ----------
def build_text():
    if not cache:
        return "📊 Loading market data..."

    p = prev_cache or cache

    return (
        "<b>📊 LIVE MARKET</b>\n\n"
        f"₿ {format_line('BTC', cache['btc'], p.get('btc'))}\n"
        f"Ξ {format_line('ETH', cache['eth'], p.get('eth'))}\n"
        f"▽ {format_line('TON', cache['ton'], p.get('ton'))}\n\n"
        f" {format_line('USD→RUB', cache['rub'], p.get('rub'), ' ₽')}\n"
        f" {format_line('USD→CNY', cache['cny'], p.get('cny'), ' ¥')}\n\n"
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

# ---------- STARTUP ----------
async def on_startup(_):
    global cache, prev_cache

    data = fetch_rates()
    if data:
        cache = data
        prev_cache = data.copy()

    asyncio.create_task(live_updater())
    asyncio.create_task(movers_poster())

# ---------- RUN ----------
if __name__ == "__main__":
    executor.start_polling(
        dp,
        skip_updates=True,
        on_startup=on_startup
    )
