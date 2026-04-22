import os
import asyncio
import requests
import logging

from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
from aiogram.utils.exceptions import MessageNotModified

# ---------- CONFIG ----------
API_TOKEN = os.getenv("API_TOKEN") or "ТВОЙ_ТОКЕН_ТУТ"
CHANNEL_ID = "@bi11ionaire"
GIF_ID = "CgACAgIAAxkBAAIFo2nouVA6zP0KFKpM0KnvY_KFODitAALumgACuo15SoosersvVltBOwQ"

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# ---------- CACHE ----------
cache = None
prev_cache = None

# ---------- UI ----------
inline_kb = InlineKeyboardMarkup().add(
    InlineKeyboardButton("🔄 Update", callback_data="update")
)

keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
keyboard.add("📊 Exchange rates", "🚀 TOP")

# ---------- API LOGIC ----------
def safe_get(url, params=None):
    try:
        r = requests.get(url, params=params, timeout=8)
        return r.json()
    except:
        return None

def get_p2p_price(fiat):
    try:
        r = requests.post(
            "https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search",
            json={"asset": "USDT", "fiat": fiat, "page": 1, "rows": 1, "tradeType": "BUY"},
            timeout=8
        ).json()
        return float(r["data"][0]["adv"]["price"]) if r.get("data") else None
    except:
        return None

def fetch_rates():
    crypto = safe_get("https://api.coingecko.com/api/v3/simple/price", 
                      params={"ids": "bitcoin,ethereum,the-open-network", "vs_currencies": "usd"})
    if not crypto: return cache

    rub = get_p2p_price("RUB") or (cache["rub"] if cache else 90)
    cny = get_p2p_price("CNY") or (cache["cny"] if cache else 7.2)

    return {
        "btc": float(crypto["bitcoin"]["usd"]),
        "eth": float(crypto["ethereum"]["usd"]),
        "ton": float(crypto["the-open-network"]["usd"]),
        "rub": rub,
        "cny": cny,
    }

def get_top_movers():
    try:
        r = safe_get("https://api.coingecko.com/api/v3/coins/markets",
                     params={"vs_currency": "usd", "order": "market_cap_desc", "per_page": 50, "page": 1, "price_change_percentage": "1h"})
        if not r: return []
        movers = [{"symbol": c["symbol"].upper(), "change": float(c["price_change_percentage_1h_in_currency"] or 0)} for c in r]
        movers.sort(key=lambda x: abs(x["change"]), reverse=True)
        return movers[:5]
    except: return []

# ---------- FORMATTING ----------
def pct(new, old):
    if not old: return 0
    return ((new - old) / old) * 100

def format_price(name, value):
    if "BTC" in name or "ETH" in name: return f"{value:,.0f}"
    return f"{value:.2f}"

def format_line(name, value, old, suffix=""):
    change = pct(value, old) if old else 0
    if abs(change) < 0.01: icon, sign = "⚪", ""
    elif change > 0: icon, sign = "🟢", "+"
    else: icon, sign = "🔴", ""
    
    return f"{name}: {format_price(name, value)}{suffix} ({sign}{change:.2f}%) {icon}"

# ---------- TEXTS ----------
def build_text():
    if not cache: return "📊 Market loading..."
    p = prev_cache if prev_cache else cache
    return (
        "<b>📊 LIVE MARKET</b>\n\n"
        f"₿ {format_line('BTC', cache['btc'], p['btc'])}\n"
        f"Ξ {format_line('ETH', cache['eth'], p['eth'])}\n"
        f"▽ {format_line('TON', cache['ton'], p['ton'])}\n\n"
        f" {format_line('USD→RUB', cache['rub'], p['rub'], ' ₽')}\n"
        f" {format_line('USD→CNY', cache['cny'], p['cny'], ' ¥')}\n\n"
        '📌 <a href="https://t.me/send?start=r-x4zoa">@CryptoBot</a>'
    )

def build_top_text():
    movers = get_top_movers()
    if not movers: return "🚀 TOP MOVERS\n\nНет данных"
    text = "🚀 <b>TOP MOVERS (1h)</b>\n\n"
    for m in movers:
        sign = "+" if m['change'] > 0 else ""
        icon = "🟢" if m['change'] > 0 else "🔴"
        text += f"<code>{m['symbol']}</code> {sign}{m['change']:.2f}% {icon}\n"
    text += "\n📌 @bi11ionaire"
    return text

# ---------- HANDLERS ----------
@dp.message_handler(commands=["start"])
async def start(m: types.Message):
    await m.answer("Choose option 👇", reply_markup=keyboard)

@dp.message_handler(lambda m: "Exchange rates" in m.text)
async def rates(m: types.Message):
    await m.answer(build_text(), reply_markup=inline_kb, parse_mode="HTML", disable_web_page_preview=True)

@dp.message_handler(lambda m: "TOP" in m.text)
async def top_btn(m: types.Message):
    text = build_top_text()
    await m.answer_animation(GIF_ID, caption=text, parse_mode="HTML")

@dp.callback_query_handler(lambda c: c.data == "update")
async def update_cb(c: types.CallbackQuery):
    try:
        await c.message.edit_text(build_text(), reply_markup=inline_kb, parse_mode="HTML", disable_web_page_preview=True)
    except MessageNotModified: pass
    await c.answer()

# ---------- LOOPS ----------
async def live_updater():
    global cache, prev_cache
    while True:
        await asyncio.sleep(150)
        data = fetch_rates()
        if data:
            prev_cache = cache.copy()
            cache = data

async def channel_poster():
    last_text = ""
    while True:
        await asyncio.sleep(300)
        if cache:
            text = build_text()
            if text != last_text:
                try:
                    await bot.send_message(CHANNEL_ID, text, parse_mode="HTML", disable_web_page_preview=True)
                    last_text = text
                except: pass

async def top_poster():
    while True:
        await asyncio.sleep(3600)
        try:
            text = build_top_text()
            await bot.send_animation(CHANNEL_ID, GIF_ID, caption=text, parse_mode="HTML")
        except: pass

# ---------- STARTUP ----------
async def on_startup(_):
    global cache, prev_cache
    data = fetch_rates()
    if data:
        cache = data
        prev_cache = data.copy()
    
    asyncio.create_task(live_updater())
    asyncio.create_task(channel_poster())
    asyncio.create_task(top_poster())

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
