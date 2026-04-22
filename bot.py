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

cache = {"btc": 0, "eth": 0, "ton": 0, "rub": 90.0, "cny": 7.0}
prev_cache = cache.copy()
top_movers_cache = "🔍 Данные загружаются..."

# ---------- DATA LOGIC ----------
def fetch_market_data():
    global cache, prev_cache
    try:
        res = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,the-open-network&vs_currencies=usd", timeout=10).json()
        def p2p(fiat):
            try:
                r = requests.post("https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search", 
                                  json={"asset":"USDT","fiat":fiat,"page":1,"rows":1,"tradeType":"BUY"}, timeout=10).json()
                return float(r["data"][0]["adv"]["price"])
            except: return None
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
    if not old or new == old: return 0
    return ((new - old) / old) * 100

def format_line(name, val, old, suffix="", is_high=False):
    price_fmt = f"{val:,.2f}" if is_high else f"{val:.2f}"
    change = get_pct(val, old)
    if abs(change) < 0.01: return f"{name}: {price_fmt}{suffix}"
    sign, icon = ("+", " 🟢") if change > 0 else ("", " 🔴")
    return f"{name}: {price_fmt}{suffix} ({sign}{change:.2f}%) {icon}"

def build_market_text():
    return (
        "<b>LIVE MARKET</b>\n\n"
        f"₿ {format_line('BTC', cache['btc'], prev_cache['btc'], is_high=True)}\n"
        f"Ξ {format_line('ETH', cache['eth'], prev_cache['eth'], is_high=True)}\n"
        f"▽ {format_line('TON', cache['ton'], prev_cache['ton'])}\n\n"
        f" {format_line('USD→RUB', cache['rub'], prev_cache['rub'], ' ₽')}\n"
        f" {format_line('USD→CNY', cache['cny'], prev_cache['cny'], ' ¥')}\n\n"
        '📌 <a href="https://t.me/send?start=r-x4zoa">@CryptoBot</a>'
    )

# ---------- HANDLERS ----------
@dp.message_handler(commands=['start'])
async def cmd_start(m: types.Message):
    await m.answer("Бот запущен!", reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add("📊 Exchange rates", "🚀 TOP"))

@dp.message_handler(lambda m: m.text and "Exchange" in m.text)
async def btn_rates(m: types.Message):
    await m.answer(build_market_text(), parse_mode="HTML", disable_web_page_preview=True)

@dp.message_handler(lambda m: m.text and "TOP" in m.text)
async def btn_top(m: types.Message):
    await m.answer_animation(GIF_ID, caption=top_movers_cache, parse_mode="HTML")

# ---------- LOOPS ----------
async def data_refresh_task():
    """Обновляет цифры в памяти каждые 2.5 минуты"""
    while True:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, fetch_market_data)
        await asyncio.sleep(150)

async def market_posting_task():
    """ТОЛЬКО 5-минутный пост LIVE MARKET"""
    while True:
        await asyncio.sleep(300) # Ждать 5 минут
        if cache['btc'] > 0:
            try:
                await bot.send_message(CHANNEL_ID, build_market_text(), parse_mode="HTML", disable_web_page_preview=True)
                logging.info("Отправлен 5-минутный пост LIVE MARKET")
            except Exception as e:
                logging.error(f"Market post error: {e}")

async def top_posting_task():
    """ТОЛЬКО часовой пост TOP MOVERS"""
    while True:
        await asyncio.sleep(3600) # Ждать 1 час
        loop = asyncio.get_event_loop()
        # Обновляем ТОП перед постингом
        txt = await loop.run_in_executor(None, fetch_top_movers)
        if txt and CHANNEL_ID:
            try:
                await bot.send_animation(CHANNEL_ID, GIF_ID, caption=txt, parse_mode="HTML")
                logging.info("Отправлен часовой пост TOP MOVERS")
            except Exception as e:
                logging.error(f"Top post error: {e}")

# ---------- STARTUP ----------
async def on_startup(_):
    # Загружаем всё при старте
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, fetch_market_data)
    await loop.run_in_executor(None, fetch_top_movers)
    
    # Делаем один приветственный пост LIVE MARKET
    try:
        await bot.send_message(CHANNEL_ID, build_market_text(), parse_mode="HTML", disable_web_page_preview=True)
    except: pass

    # Запускаем задачи
    asyncio.create_task(data_refresh_task())
    asyncio.create_task(market_posting_task())
    asyncio.create_task(top_posting_task())

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
