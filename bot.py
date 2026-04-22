import os
import asyncio
import requests
import time
import logging

from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor

# ==================== НАСТРОЙКИ ====================
API_TOKEN = os.getenv("API_TOKEN")
if not API_TOKEN:
    raise ValueError("API_TOKEN not set in environment")

CHANNEL_ID = "@bi11ionaire"

UPDATE_INTERVAL = 300
MARKET_POST_INTERVAL = 300
TOP_POST_INTERVAL = 3600

GIF_ID = "CgACAgIAAxkBAAFHyylp6HoVLUhyJVLqLnUlAAFxqwtWOR8AAu6aAAK6jXlK_gAB02c6HCOGOwQ"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# ==================== КЭШ ====================
cache = {}
prev_cache = {}
last_market_post = ""
last_top_post = ""
top_cache = ""

# ==================== КЛАВИАТУРЫ ====================
inline_kb = InlineKeyboardMarkup().add(
    InlineKeyboardButton("🔄 Update", callback_data="update")
)

keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
keyboard.add("📊 Exchange rates", "🚀 TOP")

# ==================== REQUEST ====================
def safe_get(url, params=None, retries=3):
    for _ in range(retries):
        try:
            r = requests.get(url, params=params, timeout=10)
            if r.status_code == 200:
                return r.json()
        except:
            pass
        time.sleep(1)
    return None


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


def get_top_movers():
    try:
        data = safe_get(
            "https://api.coingecko.com/api/v3/coins/markets",
            params={
                "vs_currency": "usd",
                "order": "market_cap_desc",
                "per_page": 50,
                "page": 1,
                "price_change_percentage": "1h"
            }
        )

        if not isinstance(data, list):
            return []

        movers = []
        for c in data:
            ch = c.get("price_change_percentage_1h_in_currency")
            if ch is None:
                continue

            movers.append({
                "symbol": c.get("symbol", "").upper(),
                "change": float(ch)
            })

        movers.sort(key=lambda x: abs(x["change"]), reverse=True)
        return movers[:5]

    except:
        return []


# ==================== FORMAT ====================
def pct(new, old):
    if not old:
        return 0
    return ((new - old) / old) * 100


def format_price(name, value):
    if name in ["BTC", "ETH"]:
        return f"{value:,.0f}"
    return f"{value:.2f}".replace(",", ".")


def line(sym, name, value, old, suffix=""):
    price = format_price(name, value)

    if not old:
        return f"{sym} {name}: {price}{suffix}"

    ch = pct(value, old)

    if ch > 0:
        return f"{sym} {name}: {price}{suffix} (+{ch:.2f}%) 🟢"
    elif ch < 0:
        return f"{sym} {name}: {price}{suffix} ({ch:.2f}%) 🔴"

    return f"{sym} {name}: {price}{suffix}"


def build_text():
    if not cache:
        return "📊 Loading..."

    prev = prev_cache or cache

    return (
        "<b>📊 LIVE MARKET</b>\n\n"
        f"{line('₿','BTC',cache['btc'],prev.get('btc'))}\n"
        f"{line('Ξ','ETH',cache['eth'],prev.get('eth'))}\n"
        f"{line('▽','TON',cache['ton'],prev.get('ton'))}\n\n"
        f"{line('','USD→RUB',cache['rub'],prev.get('rub'), '₽')}\n"
        f"{line('','USD→CNY',cache['cny'],prev.get('cny'), '¥')}\n\n"
        "📌 <a href='https://t.me/send?start=r-x4zoa'>@CryptoBot</a>"
    )


def build_top():
    movers = get_top_movers()

    if not movers:
        return "🚀 TOP MOVERS\n\nНет данных"

    text = "🚀 TOP MOVERS (1h)\n\n"

    for m in movers:
        sign = "+" if m["change"] > 0 else ""
        icon = "🟢" if m["change"] > 0 else "🔴"
        text += f"{m['symbol']} {sign}{m['change']:.2f}% {icon}\n"

    text += "\n📌 @bi11ionaire"
    return text


# ==================== TASKS ====================
async def updater():
    global cache, prev_cache
    while True:
        data = fetch_rates()
        if data:
            if cache:
                prev_cache = cache.copy()
            cache = data
        await asyncio.sleep(UPDATE_INTERVAL)


async def market_poster():
    global last_market_post
    while True:
        if cache:
            text = build_text()
            if text != last_market_post:
                await bot.send_message(
                    CHANNEL_ID,
                    text,
                    parse_mode="HTML",
                    disable_web_page_preview=True
                )
                last_market_post = text
        await asyncio.sleep(MARKET_POST_INTERVAL)


async def top_poster():
    global last_top_post, top_cache
    while True:
        text = build_top()
        top_cache = text

        if text != last_top_post:
            try:
                await bot.send_animation(
                    CHANNEL_ID,
                    animation=GIF_ID,
                    caption=text,
                    parse_mode="HTML"
                )
                last_top_post = text
            except Exception as e:
                logging.error(f"TOP error: {e}")

        await asyncio.sleep(TOP_POST_INTERVAL)


async def keepalive():
    while True:
        await asyncio.sleep(240)
        try:
            await bot.get_me()
        except:
            pass


# ==================== HANDLERS ====================
@dp.message_handler(commands=["start"])
async def start(m: types.Message):
    await m.answer("Choose:", reply_markup=keyboard)


@dp.message_handler(lambda m: m.text == "📊 Exchange rates")
async def rates(m: types.Message):
    await m.answer(
        build_text(),
        parse_mode="HTML",
        reply_markup=inline_kb,
        disable_web_page_preview=True
    )


@dp.message_handler(lambda m: m.text == "🚀 TOP")
async def top(m: types.Message):
    await m.answer_animation(
        animation=GIF_ID,
        caption=build_top(),
        parse_mode="HTML"
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


# ==================== START ====================
async def on_startup(_):
    asyncio.create_task(updater())
    asyncio.create_task(market_poster())
    asyncio.create_task(top_poster())
    asyncio.create_task(keepalive())


if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
