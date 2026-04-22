import os
import asyncio
import requests
import logging

from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from aiogram import F

API_TOKEN = os.getenv("API_TOKEN")
if not API_TOKEN:
    raise ValueError("API_TOKEN not set")

PORT = int(os.getenv("PORT", 8080))

CHANNEL_ID = "@bi11ionaire"
UPDATE_INTERVAL = 300
TOP_INTERVAL = 3600

GIF_ID = "CgACAgIAAxkBAAFHyylp6HoVLUhyJVLqLnUlAAFxqwtWOR8AAu6aAAK6jXlK_gAB02c6HCOGOwQ"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

cache = {}
prev_cache = {}

keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📊 Exchange rates")],
        [KeyboardButton(text="🚀 TOP")]
    ],
    resize_keyboard=True
)

inline_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Update", callback_data="update")]
    ]
)

def safe_get(url, params=None):
    try:
        r = requests.get(url, params=params, timeout=7)
        if r.status_code == 200:
            return r.json()
    except:
        pass
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
            timeout=7,
            headers={"User-Agent": "Mozilla/5.0"}
        ).json()
        return float(r["data"][0]["adv"]["price"])
    except:
        return None

def fetch_rates():
    data = safe_get(
        "https://api.coingecko.com/api/v3/simple/price",
        {"ids": "bitcoin,ethereum,the-open-network", "vs_currencies": "usd"}
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
            "vs_currency": "usd",
            "order": "market_cap_desc",
            "per_page": 50,
            "page": 1,
            "price_change_percentage": "1h"
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

def pct(new, old):
    if not old:
        return 0
    return ((new - old) / old) * 100

def line(sym, name, value, old, suffix=""):
    if not old:
        return f"{sym} {name}: {value:.2f}{suffix}"
    ch = pct(value, old)
    if ch > 0:
        return f"{sym} {name}: {value:.2f}{suffix} (+{ch:.2f}%) 🟢"
    elif ch < 0:
        return f"{sym} {name}: {value:.2f}{suffix} ({ch:.2f}%) 🔴"
    return f"{sym} {name}: {value:.2f}{suffix}"

def build_market():
    if not cache:
        return "📊 Loading..."
    prev = prev_cache or cache
    return (
        "<b>📊 LIVE MARKET</b>\n\n"
        f"{line('₿','BTC',cache['btc'],prev.get('btc'))}\n"
        f"{line('Ξ','ETH',cache['eth'],prev.get('eth'))}\n"
        f"{line('▽','TON',cache['ton'],prev.get('ton'))}\n\n"
        f"{line('','USD→RUB',cache['rub'],prev.get('rub'),' ₽')}\n"
        f"{line('','USD→CNY',cache['cny'],prev.get('cny'),' ¥')}\n\n"
        "📌 <a href='https://t.me/send?start=r-x4zoa'>@CryptoBot</a>"
    )

def build_top():
    movers = get_top()
    if not movers:
        return "🚀 TOP MOVERS\n\nНет данных"
    text = "🚀 TOP MOVERS (1h)\n\n"
    for s, ch in movers:
        sign = "+" if ch > 0 else ""
        icon = "🟢" if ch > 0 else "🔴"
        text += f"{s} {sign}{ch:.2f}% {icon}\n"
    return text

async def updater():
    global cache, prev_cache
    while True:
        try:
            data = fetch_rates()
            if data:
                if cache:
                    prev_cache = cache.copy()
                cache = data
        except Exception as e:
            logging.error(f"Updater error: {e}")
        await asyncio.sleep(UPDATE_INTERVAL)

async def top_post():
    while True:
        try:
            await bot.send_animation(CHANNEL_ID, animation=GIF_ID, caption=build_top())
        except:
            try:
                await bot.send_message(CHANNEL_ID, build_top())
            except:
                pass
        await asyncio.sleep(TOP_INTERVAL)

@dp.message(Command("start"))
async def start(m: types.Message):
    await m.answer("Choose:", reply_markup=keyboard)

@dp.message(F.text == "📊 Exchange rates")
async def rates(m: types.Message):
    await m.answer(
        build_market(),
        parse_mode="HTML",
        reply_markup=inline_kb,
        disable_web_page_preview=True
    )

@dp.message(F.text == "🚀 TOP")
async def top(m: types.Message):
    try:
        await m.answer_animation(GIF_ID, caption=build_top())
    except:
        await m.answer(build_top())

@dp.callback_query(F.data == "update")
async def update(c: types.CallbackQuery):
    await c.answer()
    await c.message.edit_text(
        build_market(),
        parse_mode="HTML",
        reply_markup=inline_kb,
        disable_web_page_preview=True
    )

from aiohttp import web

async def health_check(request):
    return web.Response(text="OK")

async def run_bot():
    """Запуск бота в отдельной корутине"""
    asyncio.create_task(updater())
    asyncio.create_task(top_post())
    await dp.start_polling(bot)

async def main():
    # Сначала запускаем веб-сервер
    app = web.Application()
    app.router.add_get("/", health_check)
    app.router.add_get("/health", health_check)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    
    print(f"Web server running on port {PORT}")
    
    # Потом запускаем бота (это блокирующая операция)
    await run_bot()

if __name__ == "__main__":
    asyncio.run(main())
