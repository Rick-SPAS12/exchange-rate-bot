except Exception as e:
        logging.error(f"get_top_movers error: {e}")
        return []


def pct(new, old):
    if not old:
        return 0
    return ((new - old) / old) * 100


def format_price(name, value):
    if name in ["BTC", "ETH"]:
        return f"{value:,.0f}".replace(",", ".")
    return f"{value:.2f}"


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

    prev = prev_cache if prev_cache else cache

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
        sign = "+"
        icon = "🟢"
        text += f"{m['symbol']} {sign}{m['change']:.2f}% {icon}\n"

    text += "\n📌 @bi11ionaire"
    return text


# ==================== ФОНОВЫЕ ЗАДАЧИ ====================
async def updater():
    global cache, prev_cache
    while True:
        data = fetch_rates()
        if data:
            if cache:
                prev_cache = cache.copy()
            cache = data
            logging.info("Rates updated")
        else:
            logging.warning("Failed to fetch rates")
        await asyncio.sleep(UPDATE_INTERVAL)


async def market_poster():
    global last_market_post
    while True:
        if cache:
            text = build_text()
            if text != last_market_post:
                try:
                    await bot.send_message(
                        CHANNEL_ID,
                        text,
                        parse_mode="HTML",
                        disable_web_page_preview=True
                    )
                    last_market_post = text
                    logging.info("Market post sent")
                except Exception as e:
                    logging.error(f"Failed to send market post: {e}")
        await asyncio.sleep(MARKET_POST_INTERVAL)


async def top_poster():
    global last_top_post
    while True:
        text = build_top()
        if text != last_top_post:
            try:
                await bot.send_message(
                    CHANNEL_ID,
                    text,
                    disable_web_page_preview=True
                )
                last_top_post = text
                logging.info("TOP post sent")
            except Exception as e:
                logging.error(f"Failed to send TOP post: {e}")
        await asyncio.sleep(TOP_POST_INTERVAL)


async def keepalive():
    while True:
        await asyncio.sleep(240)  # каждые 4 минуты
        try:
            await bot.get_me()
            logging.debug("Keepalive ping")
        except Exception as e:
            logging.warning(f"Keepalive failed: {e}")


# ==================== ОБРАБОТЧИКИ КОМАНД ====================
@dp.message_handler(commands=["start"])
async def start(m: types.Message):
    await m.answer("Choose:", reply_markup=keyboard)


@dp.message_handler(lambda m: m.text == "📊 Exchange rates")
async def rates(m: types.Message):
    await m.answer(
        build_text(),
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=inline_kb
    )


@dp.message_handler(lambda m: m.text == "🚀 TOP")
async def top(m: types.Message):
    await m.answer(
        build_top(),
        disable_web_page_preview=True
    )@dp.callback_query_handler(lambda c: c.data == "update")
async def update(c: types.CallbackQuery):
    await c.answer()
    await c.message.edit_text(
        build_text(),
        parse_mode="HTML",
        reply_markup=inline_kb,
        disable_web_page_preview=True
    )


# ==================== ЗАПУСК ====================
async def on_startup(_):
    logging.info("Bot started")
    asyncio.create_task(updater())
    asyncio.create_task(market_poster())
    asyncio.create_task(top_poster())
    asyncio.create_task(keepalive())


if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)import os
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
UPDATE_INTERVAL = 300      # 5 минут курс
MARKET_POST_INTERVAL = 300  # 5 минут пост в канал
TOP_POST_INTERVAL = 3600    # 1 час топ

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

# ==================== КЛАВИАТУРЫ ====================
inline_kb = InlineKeyboardMarkup().add(
    InlineKeyboardButton("🔄 Update", callback_data="update")
)

keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
keyboard.add("📊 Exchange rates", "🚀 TOP")

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================
def safe_get(url, params=None, retries=3):
    for attempt in range(retries):
        try:
            r = requests.get(url, params=params, timeout=10)
            if r.status_code == 200:
                return r.json()
            else:
                logging.warning(f"Attempt {attempt+1}: HTTP {r.status_code} from {url}")
        except Exception as e:
            logging.warning(f"Attempt {attempt+1} failed: {e}")

        if attempt < retries - 1:
            wait = 2 ** attempt
            logging.info(f"Retrying {url} in {wait}s...")
            time.sleep(wait)

    logging.error(f"All {retries} attempts failed for {url}")
    return None


def get_p2p_price(fiat, retries=3):
    for attempt in range(retries):
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
        except Exception as e:
            logging.warning(f"P2P attempt {attempt+1} failed: {e}")

        if attempt < retries - 1:
            wait = 2 ** attempt
            time.sleep(wait)

    logging.error(f"P2P price for {fiat} not available")
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

    rub = get_p2p_price("RUB")
    cny = get_p2p_price("CNY")

    return {
        "btc": float(crypto["bitcoin"]["usd"]),
        "eth": float(crypto["ethereum"]["usd"]),
        "ton": float(crypto["the-open-network"]["usd"]),
        "rub": rub if rub else cache.get("rub", 90),
        "cny": cny if cny else cache.get("cny", 7.2),
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
        for coin in data:
            ch = coin.get("price_change_percentage_1h_in_currency")
            if ch is None or ch <= 0:
                continue  # только рост

            movers.append({
                "symbol": coin.get("symbol", "").upper(),
                "change": float(ch)
            })

        movers.sort(key=lambda x: x["change"], reverse=True)
        return movers[:5]
