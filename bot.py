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
cache = None
prev_cache = None

# ---------- UI ----------
inline_kb = InlineKeyboardMarkup().add(
    InlineKeyboardButton("🔄 Update", callback_data="update")
)

keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
keyboard.add("📊 Exchange rates")

# ---------- SAFE REQUEST ----------
def safe_get(url, params=None):
    try:
        r = requests.get(url, params=params, timeout=10)
        if r.status_code == 200:
            return r.json()
    except:
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
        return None

# ---------- MARKET ----------
def fetch_rates():
    global cache

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
        "rub": float(rub or (cache or {}).get("rub", 90)),
        "cny": float(cny or (cache or {}).get("cny", 7.2)),
    }

# ---------- LOOP: MARKET (5 min) ----------
async def live_updater():
    global cache, prev_cache

    while True:
        try:
            data = fetch_rates()

            if data:
                prev_cache = cache.copy() if cache else data
                cache = data

        except Exception as e:
            print("UPDATE ERROR:", e)

        await asyncio.sleep(300)

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

def format_line(symbol, name, value, old, suffix=""):
    price = format_price(name, value)

    if not old:
        return f"{symbol} {name}: {price}{suffix}"

    change = pct(value, old)

    if value > old:
        return f"{symbol} {name}: {price}{suffix} (+{change:.2f}%) 🟢"
    elif value < old:
        return f"{symbol} {name}: {price}{suffix} ({change:.2f}%) 🔴"
    else:
        return f"{symbol} {name}: {price}{suffix}"

# ---------- TEXT ----------
def build_text():
    global cache, prev_cache

    if not cache:
        return "📊 Loading market data..."

    p = prev_cache or cache

    return (
        "<b>📊 LIVE MARKET</b>\n\n"
        f"{format_line('₿', 'BTC', cache['btc'], p.get('btc'))}\n"
        f"{format_line('Ξ', 'ETH', cache['eth'], p.get('eth'))}\n"
        f"{format_line('▽', 'TON', cache['ton'], p.get('ton'))}\n\n"
        f"{format_line('', 'USD→RUB', cache['rub'], p.get('rub'), ' ₽')}\n"
        f"{format_line('', 'USD→CNY', cache['cny'], p.get('cny'), ' ¥')}\n\n"
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

# ---------- CHANNEL POSTER (5 min) ----------
async def channel_poster():
    last = None

    while True:
        try:
            if not cache:
                await asyncio.sleep(5)
                continue

            text = build_text()

            if text and text != last:
                await bot.send_message(
                    CHANNEL_ID,
                    text,
                    parse_mode="HTML",
                    disable_web_page_preview=True
                )
                last = text

        except Exception as e:
            print("POST ERROR:", e)

        await asyncio.sleep(300)

# ---------- STARTUP ----------
async def on_startup(_):
    global cache, prev_cache

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
