import os
import asyncio
import requests
import logging

from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.utils.exceptions import MessageNotModified

logging.basicConfig(level=logging.INFO)

# ---------- CONFIG ----------
API_TOKEN = os.getenv("API_TOKEN") 
CHANNEL_ID = "@bi11ionaire"
GIF_ID = "CgACAgIAAxkBAAIFo2nouVA6zP0KFKpM0KnvY_KFODitAALumgACuo15SoosersvVltBOwQ"

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

cache = {"btc": 0, "eth": 0, "ton": 0, "rub": 95.0, "cny": 13.0}
prev_cache = cache.copy()
top_movers_cache = "🔍 Данные загружаются..."

# ---------- KEYBOARDS ----------
main_kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
main_kb.add("📊 Exchange rates", "🚀 TOP")

inline_kb = types.InlineKeyboardMarkup().add(
    types.InlineKeyboardButton("🔄 Update", callback_data="update")
)

# ---------- DATA LOGIC ----------
def fetch_market_data():
    global cache, prev_cache
    try:
        res = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,the-open-network&vs_currencies=usd", timeout=10).json()
        def p2p(fiat):
            r = requests.post("https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search", 
                              json={"asset":"USDT","fiat":fiat,"page":1,"rows":1,"tradeType":"BUY"}, timeout=10).json()
            return float(r["data"][0]["adv"]["price"]) if r.get("data") else None

        new_data = {
            "btc": float(res["bitcoin"]["usd"]),
            "eth": float(res["ethereum"]["usd"]),
            "ton": float(res["the-open-network"]["usd"]),
            "rub": p2p("RUB") or cache["rub"],
            "cny": p2p("CNY") or cache["cny"]
        }
        prev_cache = cache.copy()
        cache = new_data
    except Exception as e:
        logging.error(f"Error fetching: {e}")

def fetch_top_movers():
    global top_movers_cache
    try:
        r = requests.get("https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=50&page=1&price_change_percentage=1h", timeout=15).json()
        movers = [{"symbol": c["symbol"].upper(), "change": float(c["price_change_percentage_1h_in_currency"] or 0)} for c in r]
        movers.sort(key=lambda x: abs(x["change"]), reverse=True)
        txt = "🚀 <b>TOP MOVERS (1h)</b>\n\n"
        for coin in movers[:5]:
            sign = "+" if coin['change'] > 0 else ""
            icon = "🟢" if coin['change'] > 0 else "🔴"
            txt += f"<code>{coin['symbol']}</code> {sign}{coin['change']:.2f}% {icon}\n"
        txt += "\n📌 @bi11ionaire"
        top_movers_cache = txt
        return txt
    except: return top_movers_cache

# ---------- FORMATTING ----------
def get_pct(new, old):
    if not old: return 0
    return ((new - old) / old) * 100

def format_line(name, val, old, suffix=""):
    price_fmt = f"{val:,.0f}" if val > 1000 else f"{val:.2f}"
    change = get_pct(val, old)
    
    # ТВОЕ ТРЕБОВАНИЕ: Если движения нет, поле пустое
    if abs(change) < 0.01:
        return f"{name}: {price_fmt}{suffix}"
    
    icon, sign = ("🟢", "+") if change > 0 else ("🔴", "")
    return f"{name}: {price_fmt}{suffix} ({sign}{change:.2f}%) {icon}"

def build_market_text():
    return (
        "<b>📊 LIVE MARKET</b>\n\n"
        f"₿ {format_line('BTC', cache['btc'], prev_cache['btc'])}\n"
        f"Ξ {format_line('ETH', cache['eth'], prev_cache['eth'])}\n"
        f"▽ {format_line('TON', cache['ton'], prev_cache['ton'])}\n\n"
        f"💵 {format_line('USD→RUB', cache['rub'], prev_cache['rub'], ' ₽')}\n"
        f"🇨🇳 {format_line('USD→CNY', cache['cny'], prev_cache['cny'], ' ¥')}\n\n"
        '📌 <a href="https://t.me/send?start=r-x4zoa">@CryptoBot</a>'
    )

# ---------- HANDLERS ----------
@dp.message_handler(commands=['start'])
async def cmd_start(m: types.Message):
    await m.answer("Бот запущен!", reply_markup=main_kb)

@dp.message_handler(lambda m: m.text and "Exchange" in m.text)
async def btn_rates(m: types.Message):
    await m.answer(build_market_text(), parse_mode="HTML", reply_markup=inline_kb, disable_web_page_preview=True)

@dp.message_handler(lambda m: m.text and "TOP" in m.text)
async def btn_top(m: types.Message):
    await m.answer_animation(GIF_ID, caption=top_movers_cache, parse_mode="HTML")

@dp.callback_query_handler(lambda c: c.data == "update")
async def cb_update(c: types.CallbackQuery):
    try:
        await c.message.edit_text(build_market_text(), parse_mode="HTML", reply_markup=inline_kb, disable_web_page_preview=True)
    except MessageNotModified: pass
    await c.answer("Курсы обновлены")

# ---------- LOOPS ----------
async def market_loop():
    while True:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, fetch_market_data)
        await asyncio.sleep(150)

async def post_market():
    last_sent = ""
    while True:
        await asyncio.sleep(300)
        text = build_market_text()
        if text != last_sent and cache['btc'] > 0:
            try:
                await bot.send_message(CHANNEL_ID, text, parse_mode="HTML", disable_web_page_preview=True)
                last_sent = text
            except: pass

async def post_top():
    while True:
        loop = asyncio.get_event_loop()
        txt = await loop.run_in_executor(None, fetch_top_movers)
        if txt and CHANNEL_ID:
            try:
                await bot.send_animation(CHANNEL_ID, GIF_ID, caption=txt, parse_mode="HTML")
            except: pass
        await asyncio.sleep(3600)

# ---------- STARTUP ----------
async def on_startup(_):
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, fetch_market_data)
    await loop.run_in_executor(None, fetch_top_movers)
    asyncio.create_task(market_loop())
    asyncio.create_task(post_market())
    asyncio.create_task(post_top())

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
