import os
import asyncio
import requests
import logging

from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor

logging.basicConfig(level=logging.INFO)

# ---------- CONFIG ----------
API_TOKEN = os.getenv("API_TOKEN") or "PASTE_YOUR_TOKEN_HERE"
CHANNEL_ID = "@bi11ionaire"
GIF_ID = "CgACAgIAAxkBAAIFo2nouVA6zP0KFKpM0KnvY_KFODitAALumgACuo15SoosersvVltBOwQ"

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

cache = {}
prev_cache = {}
last_market_post = ""

# ---------- UI ----------
inline_kb = InlineKeyboardMarkup().add(
    InlineKeyboardButton("🔄 Update", callback_data="update")
)

keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
keyboard.add("📊 Exchange rates", "🚀 TOP")

# ---------- API FUNCTIONS ----------
def safe_get(url, params=None):
    try:
        r = requests.get(url, params=params, timeout=10)
        if r.status_code == 200: return r.json()
    except Exception as e:
        logging.error(f"Request error: {e}")
    return None

def get_p2p_price(fiat):
    try:
        r = requests.post(
            "https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search",
            json={"asset": "USDT", "fiat": fiat, "page": 1, "rows": 1, "tradeType": "BUY"},
            timeout=10
        ).json()
        if r and r.get("data"): return float(r["data"][0]["adv"]["price"])
    except: pass
    return None

def fetch_rates():
    crypto = safe_get("https://api.coingecko.com/api/v3/simple/price", 
                      params={"ids": "bitcoin,ethereum,the-open-network", "vs_currencies": "usd"})
    if not crypto: return None
    return {
        "btc": float(crypto["bitcoin"]["usd"]),
        "eth": float(crypto["ethereum"]["usd"]),
        "ton": float(crypto["the-open-network"]["usd"]),
        "rub": get_p2p_price("RUB") or cache.get("rub", 90),
        "cny": get_p2p_price("CNY") or cache.get("cny", 7.2),
    }

def get_top_movers():
    """Логика: берем топ-50, выбираем 5 самых волатильных за 1ч"""
    try:
        r = safe_get("https://api.coingecko.com/api/v3/coins/markets",
                     params={
                         "vs_currency": "usd", 
                         "order": "market_cap_desc", 
                         "per_page": 50, # Берем первые 50 монет
                         "page": 1, 
                         "price_change_percentage": "1h"
                     })
        if not r or not isinstance(r, list): return []
        
        movers = []
        for c in r:
            ch = c.get("price_change_percentage_1h_in_currency")
            if ch is not None:
                movers.append({
                    "symbol": c.get("symbol", "").upper(),
                    "change": float(ch)
                })
        
        # Сортируем по АБСОЛЮТНОМУ значению (кто больше всего пролетел вверх или вниз)
        movers.sort(key=lambda x: abs(x["change"]), reverse=True)
        return movers[:5]
    except Exception as e:
        logging.error(f"Top movers error: {e}")
        return []

# ---------- LOGIC & FORMAT ----------
def pct(new, old):
    if not old: return 0
    return ((new - old) / old) * 100

def format_price(name, value):
    if name in ["BTC", "ETH"]: return f"{value:,.0f}"
    return f"{value:.2f}"

def line(sym, name, value, old):
    price = format_price(name, value)
    if "RUB" in name: display_name = f"{name}: {price}₽"
    elif "CNY" in name: display_name = f"{name}: {price}¥"
    else: display_name = f"{sym} {name}: {price}"
    
    if not old: return display_name
    ch = pct(value, old)
    if ch > 0.01: return f"{display_name} (+{ch:.2f}%) 🟢"
    elif ch < -0.01: return f"{display_name} ({ch:.2f}%) 🔴"
    return display_name

def build_text():
    if not cache: return "📊 Loading..."
    p = prev_cache or cache
    return (
        "<b>📊 LIVE MARKET</b>\n\n"
        f"{line('₿','BTC',cache['btc'],p.get('btc', cache['btc']))}\n"
        f"{line('Ξ','ETH',cache['eth'],p.get('eth', cache['eth']))}\n"
        f"{line('▽','TON',cache['ton'],p.get('ton', cache['ton']))}\n\n"
        f"{line('','USD→RUB',cache['rub'],p.get('rub', cache['rub']))}\n"
        f"{line('','USD→CNY',cache['cny'],p.get('cny', cache['cny']))}\n\n"
        "📌 <a href='https://t.me/send?start=r-x4zoa'>@CryptoBot</a>"
    )

def build_top():
    movers = get_top_movers()
    if not movers: return "🚀 TOP MOVERS\n\nНет данных от API"
    text = "🚀 <b>TOP MOVERS (1h)</b>\n\n"
    for m in movers:
        icon = "🟢" if m["change"] > 0 else "🔴"
        sign = "+" if m["change"] > 0 else ""
        text += f"<code>{m['symbol']}</code> {sign}{m['change']:.2f}% {icon}\n"
    text += "\n📌 @bi11ionaire"
    return text

# ---------- ASYNC TASKS ----------
async def updater():
    global cache, prev_cache
    while True:
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, fetch_rates)
        if data:
            prev_cache = cache.copy() if cache else data
            cache = data
        await asyncio.sleep(150)

async def market_poster():
    global last_market_post
    while True:
        await asyncio.sleep(300)
        if cache:
            text = build_text()
            if text != last_market_post:
                try:
                    await bot.send_message(CHANNEL_ID, text, parse_mode="HTML", disable_web_page_preview=True)
                    last_market_post = text
                except: pass

async def top_poster():
    while True:
        await asyncio.sleep(3600)
        loop = asyncio.get_event_loop()
        text = await loop.run_in_executor(None, build_top)
        try:
            await bot.send_animation(CHANNEL_ID, GIF_ID, caption=text, parse_mode="HTML")
        except: pass

# ---------- HANDLERS ----------
@dp.message_handler(commands=["start"])
async def start(m: types.Message):
    await m.answer("Choose:", reply_markup=keyboard)

@dp.message_handler(lambda m: m.text and "Exchange" in m.text)
async def rates_handler(m: types.Message):
    await m.answer(build_text(), parse_mode="HTML", disable_web_page_preview=True, reply_markup=inline_kb)

@dp.message_handler(lambda m: m.text and "TOP" in m.text)
async def top_handler(m: types.Message):
    # Вызываем асинхронно, чтобы не тормозить бота
    loop = asyncio.get_event_loop()
    text = await loop.run_in_executor(None, build_top)
    await m.answer_animation(GIF_ID, caption=text, parse_mode="HTML")

@dp.callback_query_handler(lambda c: c.data == "update")
async def update_cb(c: types.CallbackQuery):
    try:
        await c.message.edit_text(build_text(), parse_mode="HTML", reply_markup=inline_kb, disable_web_page_preview=True)
    except: pass
    await c.answer()

async def on_startup(_):
    asyncio.create_task(updater())
    asyncio.create_task(market_poster())
    asyncio.create_task(top_poster())

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
