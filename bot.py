import os
import asyncio
import requests
import logging

from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.utils.exceptions import MessageNotModified

# Логирование для отладки в Railway
logging.basicConfig(level=logging.INFO)

# ---------- CONFIG ----------
API_TOKEN = os.getenv("API_TOKEN") # Переменная в Railway
CHANNEL_ID = "@bi11ionaire"
GIF_ID = "CgACAgIAAxkBAAIFo2nouVA6zP0KFKpM0KnvY_KFODitAALumgACuo15SoosersvVltBOwQ"

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# Кэш данных
cache = {"btc":0, "eth":0, "ton":0, "rub":90, "cny":7.2}
prev_cache = cache.copy()

# ---------- KEYBOARDS ----------
main_kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
main_kb.add("📊 Exchange rates", "🚀 TOP")

inline_kb = types.InlineKeyboardMarkup().add(
    types.InlineKeyboardButton("🔄 Update", callback_data="update")
)

# ---------- DATA LOGIC ----------
def get_market_data():
    try:
        # Крипта
        res = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,the-open-network&vs_currencies=usd", timeout=10).json()
        
        # P2P через Binance
        def p2p(fiat):
            r = requests.post("https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search", 
                              json={"asset":"USDT","fiat":fiat,"page":1,"rows":1,"tradeType":"BUY"}, timeout=10).json()
            return float(r["data"][0]["adv"]["price"]) if r.get("data") else None

        return {
            "btc": float(res["bitcoin"]["usd"]),
            "eth": float(res["ethereum"]["usd"]),
            "ton": float(res["the-open-network"]["usd"]),
            "rub": p2p("RUB") or cache["rub"],
            "cny": p2p("CNY") or cache["cny"]
        }
    except:
        return None

def get_top_movers():
    try:
        r = requests.get("https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=50&page=1&price_change_percentage=1h", timeout=10).json()
        # Собираем данные по топ-50
        movers = [{"symbol": c["symbol"].upper(), "change": float(c["price_change_percentage_1h_in_currency"] or 0)} for c in r]
        # Сортируем по самому мощному движению (модуль числа)
        movers.sort(key=lambda x: abs(x["change"]), reverse=True)
        return movers[:5]
    except:
        return []

# ---------- FORMATTING ----------
def get_pct(new, old):
    if not old: return 0
    return ((new - old) / old) * 100

def format_line(name, val, old, suffix=""):
    price_fmt = f"{val:,.0f}" if val > 1000 else f"{val:.2f}"
    change = get_pct(val, old)
    
    if abs(change) < 0.01: icon, sign = "⚪", ""
    elif change > 0: icon, sign = "🟢", "+"
    else: icon, sign = "🔴", ""
    
    return f"{name}: {price_fmt}{suffix} ({sign}{change:.2f}%) {icon}"

def build_market_text():
    p = prev_cache
    return (
        "<b>📊 LIVE MARKET</b>\n\n"
        f"₿ {format_line('BTC', cache['btc'], p['btc'])}\n"
        f"Ξ {format_line('ETH', cache['eth'], p['eth'])}\n"
        f"▽ {format_line('TON', cache['ton'], p['ton'])}\n\n"
        f" {format_line('USD→RUB', cache['rub'], p['rub'], ' ₽')}\n"
        f" {format_line('USD→CNY', cache['cny'], p['cny'], ' ¥')}\n\n"
        '📌 <a href="https://t.me/send?start=r-x4zoa">@CryptoBot</a>'
    )

# ---------- HANDLERS ----------
@dp.message_handler(commands=['start'])
async def cmd_start(m: types.Message):
    await m.answer("Бот запущен! Используй меню ниже 👇", reply_markup=main_kb)

@dp.message_handler(lambda m: "Exchange rates" in m.text)
async def btn_rates(m: types.Message):
    await m.answer(build_market_text(), parse_mode="HTML", reply_markup=inline_kb, disable_web_page_preview=True)

@dp.message_handler(lambda m: "TOP" in m.text)
async def btn_top(m: types.Message):
    loop = asyncio.get_event_loop()
    movers = await loop.run_in_executor(None, get_top_movers)
    
    if not movers:
        return await m.answer("⚠️ Не удалось загрузить данные ТОП-50.")
    
    txt = "🚀 <b>TOP MOVERS (1h)</b>\n\n"
    for coin in movers:
        sign = "+" if coin['change'] > 0 else ""
        icon = "🟢" if coin['change'] > 0 else "🔴"
        txt += f"<code>{coin['symbol']}</code> {sign}{coin['change']:.2f}% {icon}\n"
    txt += "\n📌 @bi11ionaire"
    
    await m.answer_animation(GIF_ID, caption=txt, parse_mode="HTML")

@dp.callback_query_handler(lambda c: c.data == "update")
async def cb_update(c: types.CallbackQuery):
    try:
        await c.message.edit_text(build_market_text(), parse_mode="HTML", reply_markup=inline_kb, disable_web_page_preview=True)
    except MessageNotModified:
        pass
    await c.answer("Курсы обновлены")

# ---------- LOOPS ----------
async def update_data_loop():
    global cache, prev_cache
    while True:
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, get_market_data)
        if data:
            prev_cache = cache.copy()
            cache = data
        await asyncio.sleep(150) # раз в 2.5 минуты

async def auto_post_market():
    last_sent = ""
    while True:
        await asyncio.sleep(300) # раз в 5 минут
        text = build_market_text()
        if text != last_sent:
            try:
                await bot.send_message(CHANNEL_ID, text, parse_mode="HTML", disable_web_page_preview=True)
                last_sent = text
            except: pass

async def auto_post_top():
    while True:
        await asyncio.sleep(3600) # раз в час
        loop = asyncio.get_event_loop()
        movers = await loop.run_in_executor(None, get_top_movers)
        if movers:
            txt = "🚀 <b>TOP MOVERS (1h)</b>\n\n"
            for coin in movers:
                sign = "+" if coin['change'] > 0 else ""
                icon = "🟢" if coin['change'] > 0 else "🔴"
                txt += f"<code>{coin['symbol']}</code> {sign}{coin['change']:.2f}% {icon}\n"
            txt += "\n📌 @bi11ionaire"
            try:
                await bot.send_animation(CHANNEL_ID, GIF_ID, caption=txt, parse_mode="HTML")
            except: pass

# ---------- STARTUP ----------
async def on_startup(_):
    # Первичная загрузка
    global cache, prev_cache
    data = get_market_data()
    if data:
        cache = data
        prev_cache = data.copy()
    
    asyncio.create_task(update_data_loop())
    asyncio.create_task(auto_post_market())
    asyncio.create_task(auto_post_top())

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
