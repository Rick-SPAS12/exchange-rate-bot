import os
import asyncio
import requests
import logging

from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
from aiogram.utils.exceptions import MessageNotModified

logging.basicConfig(level=logging.INFO)

API_TOKEN = os.getenv("API_TOKEN")
if not API_TOKEN:
    raise ValueError("API_TOKEN не найден")

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

CHANNEL_ID = "@bi11ionaire"
TOP_GIF_ID = "CgACAgIAAxkBAAIFo2nouVA6zP0KFKpM0KnvY_KFODitAALumgACuo15SoosersvVltBOwQ"

cache = {}
prev_cache = {}

inline_kb = InlineKeyboardMarkup().add(
    InlineKeyboardButton("🔄 Update", callback_data="update")
)

keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
keyboard.add("📊 Exchange rates", "🚀 TOP")

# ---------- REQUESTS ----------
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
        if r.get("data"):
            return float(r["data"][0]["adv"]["price"])
    except:
        pass
    return None

def fetch_rates():
    data = safe_get(
        "https://api.coingecko.com/api/v3/simple/price",
        {"ids":"bitcoin,ethereum,the-open-network","vs_currencies":"usd"}
    )
    if not data:
        return None

    rub = get_p2p_price("RUB") or (cache.get("rub") if cache else 90.0)
    cny = get_p2p_price("CNY") or (cache.get("cny") if cache else 7.2)

    return {
        "btc": float(data["bitcoin"]["usd"]),
        "eth": float(data["ethereum"]["usd"]),
        "ton": float(data["the-open-network"]["usd"]),
        "rub": rub,
        "cny": cny,
    }

def get_top():
    data = safe_get(
        "https://api.coingecko.com/api/v3/coins/markets",
        {"vs_currency":"usd","order":"market_cap_desc","per_page":50,"page":1,"price_change_percentage":"1h"}
    )
    if not data:
        return []

    movers = []
    for c in data:
        ch = c.get("price_change_percentage_1h_in_currency")
        if ch is not None:
            movers.append((c["symbol"].upper(), float(ch)))

    movers.sort(key=lambda x: abs(x[1]), reverse=True)
    return movers[:5]

# ---------- FORMAT ----------
def format_crypto(value):
    return f"{value:,.0f}".replace(",", ".")

def format_fiat(value):
    return f"{value:,.2f}".replace(",", ".")

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
        return "🚀 TOP MOVERS (1h)\n\nНет данных"

    text = "🚀 TOP MOVERS (1h)\n\n"
    for s, ch in movers:
        icon = "🟢" if ch > 0 else "🔴"
        sign = "+" if ch > 0 else ""
        text += f"{s} {sign}{ch:.2f}% {icon}\n"
    text += "\n📌 @bi11ionaire"
    return text

# ---------- TASKS ----------
async def updater():
    global cache, prev_cache
    while True:
        data = fetch_rates()
        if data:
            if cache:
                prev_cache = cache.copy()
            cache = data
            logging.info("Cache updated")
        await asyncio.sleep(300)

async def market_poster():
    while not cache:
        await asyncio.sleep(1)
    while True:
        try:
            await bot.send_message(CHANNEL_ID, build_market(), parse_mode="HTML")
            logging.info("Market posted")
        except Exception as e:
            logging.error(f"Market post error: {e}")
        await asyncio.sleep(300)

async def top_poster():
    while True:
        try:
            await bot.send_animation(CHANNEL_ID, TOP_GIF_ID, caption=build_top(), parse_mode="HTML")
            logging.info("Top posted")
        except Exception as e:
            logging.error(f"Top post error: {e}")
        await asyncio.sleep(3600)

# ---------- HANDLERS ----------
@dp.message_handler(commands=["start"])
async def start(m: types.Message):
    await m.answer("Выбери:", reply_markup=keyboard)

@dp.message_handler(lambda m: m.text == "📊 Exchange rates")
async def rates(m: types.Message):
    await m.answer(build_market(), parse_mode="HTML", reply_markup=inline_kb)

@dp.message_handler(lambda m: m.text == "🚀 TOP")
async def top(m: types.Message):
    try:
        await m.answer_animation(TOP_GIF_ID, caption=build_top(), parse_mode="HTML")
    except:
        await m.answer(build_top())

@dp.callback_query_handler(lambda c: c.data == "update")
async def update(c: types.CallbackQuery):
    await c.answer()
    try:
        await c.message.edit_text(build_market(), parse_mode="HTML", reply_markup=inline_kb)
    except MessageNotModified:
        pass
    except:
        pass

# ---------- START ----------
async def on_startup(_):
    data = fetch_rates()
    if data:
        global cache
        cache = data
    asyncio.create_task(updater())
    asyncio.create_task(market_poster())
    asyncio.create_task(top_poster())

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
