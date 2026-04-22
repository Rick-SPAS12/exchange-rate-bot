import os
import asyncio
import requests
import logging

from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor

API_TOKEN = os.getenv("API_TOKEN")
CHANNEL_ID = "@bi11ionaire"

UPDATE_INTERVAL = 300
TOP_INTERVAL = 3600

GIF_ID = "CgACAgIAAxkBAAIFo2nouVA6zP0KFKpM0KnvY_KFODitAALumgACuo15SoosersvVltBOwQ"

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

cache = {}
prev_cache = {}

keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
keyboard.add("📊 Exchange rates", "🚀 TOP MOVERS")

inline_kb = InlineKeyboardMarkup().add(
    InlineKeyboardButton("🔄 Update", callback_data="update")
)

# ================= FORMAT =================
def format_crypto(value):
    return f"{value:,.0f}".replace(",", ".")

def format_fiat(value):
    return f"{value:,.2f}"

def pct(new, old):
    if not old:
        return 0
    return ((new - old) / old) * 100

def line(sym, name, value, old, is_crypto=False):
    if is_crypto:
        val = format_crypto(value)
    else:
        val = format_fiat(value)

    if not old:
        return f"{sym} {name}: {val}"

    ch = pct(value, old)

    if ch > 0:
        return f"{sym} {name}: {val} (+{ch:.2f}%) 🟢"
    elif ch < 0:
        return f"{sym} {name}: {val} ({ch:.2f}%) 🔴"

    return f"{sym} {name}: {val}"

# ================= REQUESTS =================
def safe_get(url, params=None):
    try:
        r = requests.get(url, params=params, timeout=10)
        if r.status_code == 200:
            return r.json()
    except:
        pass
    return None

def get_p2p_price(fiat):
    try:
        r = requests.post(
            "https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search",
            json={"asset":"USDT","fiat":fiat,"page":1,"rows":1,"tradeType":"BUY"},
            timeout=10
        ).json()
        return float(r["data"][0]["adv"]["price"])
    except:
        return None

# ================= DATA =================
def fetch_rates():
    data = safe_get(
        "https://api.coingecko.com/api/v3/simple/price",
        {"ids":"bitcoin,ethereum,the-open-network","vs_currencies":"usd"}
    )
    if not data:
        return None

    return {
        "btc": float(data["bitcoin"]["usd"]),
        "eth": float(data["ethereum"]["usd"]),
        "ton": float(data["the-open-network"]["usd"]),
        "rub": get_p2p_price("RUB") or cache.get("rub", 90),
        "cny": get_p2p_price("CNY") or cache.get("cny", 7.2),
    }

def get_top():
    data = safe_get(
        "https://api.coingecko.com/api/v3/coins/markets",
        {
            "vs_currency":"usd",
            "order":"market_cap_desc",
            "per_page":50,
            "page":1,
            "price_change_percentage":"1h"
        }
    )
    if not data:
        return []

    movers = []
    for c in data:
        ch = c.get("price_change_percentage_1h_in_currency")
        if ch is None:
            continue
        movers.append((c["symbol"].upper(), float(ch)))

    movers.sort(key=lambda x: abs(x[1]), reverse=True)
    return movers[:5]

# ================= TEXT =================
def build_market():
    if not cache:
        return "📊 Loading..."

    prev = prev_cache or cache

    return (
        "<b>📊 LIVE MARKET</b>\n\n"
        f"{line('₿','BTC',cache['btc'],prev.get('btc'),True)}\n"
        f"{line('Ξ','ETH',cache['eth'],prev.get('eth'),True)}\n"
        f"{line('▽','TON',cache['ton'],prev.get('ton'),True)}\n\n"
        f"{line('','USD→RUB',cache['rub'],prev.get('rub'))} ₽\n"
        f"{line('','USD→CNY',cache['cny'],prev.get('cny'))} ¥\n\n"
        "📌 <a href='https://t.me/send?start=r-x4zoa'>@CryptoBot</a>"
    )

def build_top():
    movers = get_top()

    if not movers:
        return "<b>🚀 TOP MOVERS (1h)</b>\n\nNo data"

    text = "<b>🚀 TOP MOVERS (1h)</b>\n\n"
    for s, ch in movers:
        sign = "+" if ch > 0 else ""
        icon = "🟢" if ch > 0 else "🔴"
        text += f"{s} {sign}{ch:.2f}% {icon}\n"

    return text

# ================= TASKS =================
async def updater():
    global cache, prev_cache
    while True:
        data = fetch_rates()
        if data:
            if cache:
                prev_cache = cache.copy()
            cache = data
        await asyncio.sleep(UPDATE_INTERVAL)

async def market_post():
    while True:
        try:
            await bot.send_message(CHANNEL_ID, build_market(), parse_mode="HTML")
        except Exception as e:
            logging.error(e)
        await asyncio.sleep(UPDATE_INTERVAL)

async def top_post():
    while True:
        try:
            await bot.send_animation(CHANNEL_ID, GIF_ID, caption=build_top(), parse_mode="HTML")
        except Exception as e:
            logging.error(e)
        await asyncio.sleep(TOP_INTERVAL)

# ================= HANDLERS =================
@dp.message_handler(commands=["start"])
async def start(m: types.Message):
    await m.answer("Choose:", reply_markup=keyboard)

@dp.message_handler(lambda m: m.text == "📊 Exchange rates")
async def rates(m: types.Message):
    await m.answer(build_market(), parse_mode="HTML", reply_markup=inline_kb)

@dp.message_handler(lambda m: m.text == "🚀 TOP MOVERS")
async def top(m: types.Message):
    await m.answer_animation(GIF_ID, caption=build_top(), parse_mode="HTML")

@dp.callback_query_handler(lambda c: c.data == "update")
async def update(c: types.CallbackQuery):
    await c.answer()
    await c.message.edit_text(build_market(), parse_mode="HTML", reply_markup=inline_kb)

# ================= START =================
async def on_startup(_):
    asyncio.create_task(updater())
    asyncio.create_task(market_post())
    asyncio.create_task(top_post())

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
