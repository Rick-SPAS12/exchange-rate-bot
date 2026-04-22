import os
import asyncio
import requests
import logging
import time

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

state = {
    "cache": {"btc": 0, "eth": 0, "ton": 0, "rub": 90.0, "cny": 7.0},
    "prev_cache": {"btc": 0, "eth": 0, "ton": 0, "rub": 90.0, "cny": 7.0},
    "top_movers_text": "🔍 Загрузка данных..."
}

# ---------- DATA LOGIC ----------
def fetch_data():
    try:
        res = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,the-open-network&vs_currencies=usd", timeout=10).json()
        def p2p(fiat):
            try:
                r = requests.post("https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search", 
                                  json={"asset":"USDT","fiat":fiat,"page":1,"rows":1,"tradeType":"BUY"}, timeout=10).json()
                return float(r["data"][0]["adv"]["price"])
            except: return None

        state["prev_cache"] = state["cache"].copy()
        state["cache"] = {
            "btc": float(res["bitcoin"]["usd"]),
            "eth": float(res["ethereum"]["usd"]),
            "ton": float(res["the-open-network"]["usd"]),
            "rub": p2p("RUB") or state["cache"]["rub"],
            "cny": p2p("CNY") or state["cache"]["cny"]
        }
        
        r_top = requests.get("https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=50&page=1&price_change_percentage=1h", timeout=10).json()
        movers = [{"symbol": c["symbol"].upper(), "change": float(c["price_change_percentage_1h_in_currency"] or 0)} for c in r_top]
        movers.sort(key=lambda x: abs(x["change"]), reverse=True)
        txt = "🚀 <b>TOP MOVERS (1h)</b>\n\n"
        for coin in movers[:5]:
            sign, icon = ("+", "🟢") if coin['change'] > 0 else ("", "🔴")
            txt += f"<code>{coin['symbol']}</code> {sign}{coin['change']:.2f}% {icon}\n"
        txt += "\n📌 @bi11ionaire"
        state["top_movers_text"] = txt
    except Exception as e:
        logging.error(f"Fetch error: {e}")

# ---------- FORMATTING ----------
def format_line(name, val, old, suffix="", is_high=False):
    price_fmt = f"{val:,.2f}" if is_high else f"{val:.2f}"
    change = ((val - old) / old * 100) if old and val != old else 0
    if abs(change) < 0.01: return f"{name}: {price_fmt}{suffix}"
    sign, icon = ("+", " 🟢") if change > 0 else ("", " 🔴")
    return f"{name}: {price_fmt}{suffix} ({sign}{change:.2f}%) {icon}"

def build_market_text():
    c, p = state["cache"], state["prev_cache"]
    return (
        "<b>LIVE MARKET</b>\n\n"
        f"₿ {format_line('BTC', c['btc'], p['btc'], is_high=True)}\n"
        f"Ξ {format_line('ETH', c['eth'], p['eth'], is_high=True)}\n"
        f"▽ {format_line('TON', c['ton'], p['ton'])}\n\n"
        f" {format_line('USD→RUB', c['rub'], p['rub'], ' ₽')}\n"
        f" {format_line('USD→CNY', c['cny'], p['cny'], ' ¥')}\n\n"
        '📌 <a href="https://t.me/send?start=r-x4zoa">@CryptoBot</a>'
    )

# ---------- HANDLERS ----------
@dp.message_handler(commands=['start'])
async def cmd_start(m: types.Message):
    await m.answer("Бот активен!", reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add("📊 Exchange rates", "🚀 TOP"))

@dp.message_handler(lambda m: m.text and "Exchange" in m.text)
async def btn_rates(m: types.Message):
    await m.answer(build_market_text(), parse_mode="HTML", disable_web_page_preview=True)

@dp.message_handler(lambda m: m.text and "TOP" in m.text)
async def btn_top(m: types.Message):
    await m.answer_animation(GIF_ID, caption=state["top_movers_text"], parse_mode="HTML")

# ---------- INDEPENDENT CYCLES ----------

async def update_data_loop():
    """Обновление цифр каждые 2 минуты"""
    while True:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, fetch_data)
        await asyncio.sleep(120)

async def market_post_loop():
    """Жестко: раз в 5 минут"""
    while True:
        await asyncio.sleep(300) # Интервал 5 минут
        if state["cache"]["btc"] > 0:
            try:
                await bot.send_message(CHANNEL_ID, build_market_text(), parse_mode="HTML", disable_web_page_preview=True)
                logging.info("Отправлен Маркет")
            except: pass

async def top_post_loop():
    """Жестко: раз в 1 час"""
    while True:
        await asyncio.sleep(3600) # Интервал 1 час
        if "🚀" in state["top_movers_text"]:
            try:
                await bot.send_animation(CHANNEL_ID, GIF_ID, caption=state["top_movers_text"], parse_mode="HTML")
                logging.info("Отправлен ТОП")
            except: pass

# ---------- STARTUP ----------
async def on_startup(_):
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, fetch_data)
    
    # Запускаем задачи ПО ОТДЕЛЬНОСТИ
    asyncio.create_task(update_data_loop())
    asyncio.create_task(market_post_loop())
    asyncio.create_task(top_post_loop())

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
