import os
import asyncio
import aiohttp
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Настройка логирования, чтобы видеть ошибки в консоли
logging.basicConfig(level=logging.INFO)

# ---------- TOKEN ----------
API_TOKEN = os.getenv("API_TOKEN") or "PASTE_YOUR_TOKEN_HERE"

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# ---------- CHANNEL ----------
CHANNEL_ID = "@bi11ionaire"

# ---------- CACHE ----------
cache = {}
prev_cache = {}
last_market_post = ""
last_top_post = ""

# ---------- UI ----------
inline_kb = InlineKeyboardMarkup().add(
    InlineKeyboardButton("🔄 Update", callback_data="update")
)

keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
keyboard.add("📊 Exchange rates", "🚀 TOP")

# ---------- ASYNC REQUESTS ----------
async def safe_get(session, url, params=None):
    try:
        async with session.get(url, params=params, timeout=10) as response:
            if response.status == 200:
                return await response.json()
    except Exception as e:
        logging.error(f"Error fetching {url}: {e}")
    return None

async def get_p2p_price(session, fiat):
    url = "https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search"
    payload = {
        "asset": "USDT",
        "fiat": fiat,
        "page": 1,
        "rows": 1,
        "tradeType": "BUY"
    }
    try:
        async with session.post(url, json=payload, timeout=10) as response:
            r = await response.json()
            if r and r.get("data"):
                return float(r["data"][0]["adv"]["price"])
    except Exception as e:
        logging.error(f"P2P Error ({fiat}): {e}")
    return None

# ---------- DATA FETCHING ----------
async def fetch_rates():
    async with aiohttp.ClientSession() as session:
        crypto_task = safe_get(session, "https://api.coingecko.com/api/v3/simple/price", 
                              params={"ids": "bitcoin,ethereum,the-open-network", "vs_currencies": "usd"})
        
        rub_task = get_p2p_price(session, "RUB")
        cny_task = get_p2p_price(session, "CNY")
        
        crypto, rub, cny = await asyncio.gather(crypto_task, rub_task, cny_task)

        if not crypto:
            return None

        return {
            "btc": float(crypto["bitcoin"]["usd"]),
            "eth": float(crypto["ethereum"]["usd"]),
            "ton": float(crypto["the-open-network"]["usd"]),
            "rub": rub or cache.get("rub", 90),
            "cny": cny or cache.get("cny", 7.2),
        }

async def get_top_movers():
    async with aiohttp.ClientSession() as session:
        r = await safe_get(session, "https://api.coingecko.com/api/v3/coins/markets", 
                          params={
                              "vs_currency": "usd",
                              "order": "market_cap_desc",
                              "per_page": 50,
                              "page": 1,
                              "price_change_percentage": "1h"
                          })
        if not r or not isinstance(r, list):
            return []

        movers = []
        for c in r:
            ch = c.get("price_change_percentage_1h_in_currency")
            if ch is not None:
                movers.append({"symbol": c.get("symbol", "").upper(), "change": float(ch)})

        movers.sort(key=lambda x: abs(x["change"]), reverse=True)
        return movers[:5]

# ---------- FORMATTING ----------
def pct(new, old):
    if not old or old == 0: return 0
    return ((new - old) / old) * 100

def format_price(name, value):
    if name in ["BTC", "ETH"]:
        return f"{value:,.0f}".replace(",", " ") # Красивый пробел вместо запятой
    return f"{value:.2f}"

def line(sym, name, value, old):
    price = format_price(name, value)
    if not old or value == old:
        return f"{sym} {name}: {price}"
    
    ch = pct(value, old)
    if ch > 0:
        return f"{sym} {name}: {price} (+{ch:.2f}%) 🟢"
    elif ch < 0:
        return f"{sym} {name}: {price} ({ch:.2f}%) 🔴"
    return f"{sym} {name}: {price}"

def build_text():
    if not cache:
        return "📊 Loading..."
    p = prev_cache if prev_cache else cache
    return (
        "<b>📊 LIVE MARKET</b>\n\n"
        f"{line('₿','BTC',cache['btc'], p.get('btc'))}\n"
        f"{line('Ξ','ETH',cache['eth'], p.get('eth'))}\n"
        f"{line('▽','TON',cache['ton'], p.get('ton'))}\n\n"
        f"{line('₽','USD→RUB',cache['rub'], p.get('rub'))}\n"
        f"{line('¥','USD→CNY',cache['cny'], p.get('cny'))}\n\n"
        "📌 <a href='https://t.me/send?start=r-x4zoa'>@CryptoBot</a>"
    )

async def build_top_text():
    movers = await get_top_movers()
    if not movers: return "🚀 TOP MOVERS\n\nНет данных"
    text = "🚀 TOP MOVERS (1h)\n\n"
    for m in movers:
        icon = "🟢" if m['change'] > 0 else "🔴"
        sign = "+" if m['change'] > 0 else ""
        text += f"{m['symbol']} {sign}{m['change']:.2f}% {icon}\n"
    text += "\n📌 @bi11ionaire"
    return text

# ---------- LOOPS ----------
async def updater():
    global cache, prev_cache
    while True:
        data = await fetch_rates()
        if data:
            if cache:
                prev_cache = cache.copy()
            cache = data
        await asyncio.sleep(300)

async def market_poster():
    global last_market_post
    while True:
        await asyncio.sleep(300) # Ждем перед следующей проверкой
        if cache:
            text = build_text()
            if text != last_market_post:
                try:
                    await bot.send_message(CHANNEL_ID, text, parse_mode="HTML", disable_web_page_preview=True)
                    last_market_post = text
                except Exception as e:
                    logging.error(f"Post error: {e}")

async def top_poster():
    global last_top_post
    while True:
        await asyncio.sleep(3600)
        text = await build_top_text()
        if text != last_top_post:
            try:
                await bot.send_message(CHANNEL_ID, text, disable_web_page_preview=True)
                last_top_post = text
            except Exception as e:
                logging.error(f"Top post error: {e}")

# ---------- HANDLERS ----------
@dp.message_handler(commands=["start"])
async def start(m: types.Message):
    await m.answer("Choose:", reply_markup=keyboard)

@dp.message_handler(lambda m: m.text and "Exchange" in m.text)
async def rates(m: types.Message):
    await m.answer(build_text(), parse_mode="HTML", disable_web_page_preview=True, reply_markup=inline_kb)

@dp.message_handler(lambda m: m.text and "TOP" in m.text)
async def top_cmd(m: types.Message):
    text = await build_top_text()
    await m.answer(text, disable_web_page_preview=True)

@dp.callback_query_handler(lambda c: c.data == "update")
async def update_cb(c: types.CallbackQuery):
    await c.answer("Updating...")
    await c.message.edit_text(build_text(), parse_mode="HTML", reply_markup=inline_kb, disable_web_page_preview=True)

async def on_startup(_):
    asyncio.create_task(updater())
    asyncio.create_task(market_poster())
    asyncio.create_task(top_poster())

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
