import os
import asyncio
import requests
import logging

from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor

# ---------- LOGGING ----------
logging.basicConfig(level=logging.INFO)

# ---------- TOKEN ----------
API_TOKEN = os.getenv("API_TOKEN")
if not API_TOKEN:
    raise ValueError("API_TOKEN не найден в переменных окружения!")

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# ---------- CHANNEL ----------
CHANNEL_ID = "@bi11ionaire"

# ---------- GIF ----------
TOP_GIF_ID = "CgACAgIAAxkBAAIFo2nouVA6zP0KFKpM0KnvY_KFODitAALumgACuo15SoosersvVltBOwQ"

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

# ---------- SAFE REQUEST ----------
def safe_get(url, params=None):
    try:
        r = requests.get(url, params=params, timeout=10)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        logging.error(f"safe_get error: {e}")
    return None

# ---------- P2P ----------
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
    except Exception as e:
        logging.error(f"get_p2p_price error for {fiat}: {e}")
    return None

# ---------- MARKET ----------
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
        "rub": rub if rub else cache.get("rub", 90.0),
        "cny": cny if cny else cache.get("cny", 7.2),
    }

# ---------- TOP MOVERS ----------
def get_top_movers():
    try:
        r = safe_get(
            "https://api.coingecko.com/api/v3/coins/markets",
            params={
                "vs_currency": "usd",
                "order": "market_cap_desc",
                "per_page": 50,
                "page": 1,
                "price_change_percentage": "1h"
            }
        )

        if not isinstance(r, list):
            return []

        movers = []

        for c in r:
            ch = c.get("price_change_percentage_1h_in_currency")
            if ch is None:
                continue

            movers.append({
                "symbol": c.get("symbol", "").upper(),
                "change": float(ch)
            })

        movers.sort(key=lambda x: abs(x["change"]), reverse=True)
        return movers[:5]

    except Exception as e:
        logging.error(f"get_top_movers error: {e}")
        return []

# ---------- FORMAT ----------
def pct(new, old):
    if not old:
        return 0
    return ((new - old) / old) * 100

def format_crypto(value):
    return f"{value:,.0f}".replace(",", ".")

def format_fiat(value):
    return f"{value:,.2f}".replace(",", ".")

def build_text():
    if not cache:
        return "📊 Loading..."

    p = prev_cache if prev_cache else cache

    text = "<b>📊 LIVE MARKET</b>\n\n"

    # BTC
    btc = format_crypto(cache['btc'])
    btc_old = p.get('btc')
    if btc_old:
        ch = pct(cache['btc'], btc_old)
        if ch > 0:
            text += f"₿ BTC: {btc} (+{ch:.2f}%) 🟢\n"
        elif ch < 0:
            text += f"₿ BTC: {btc} ({ch:.2f}%) 🔴\n"
        else:
            text += f"₿ BTC: {btc}\n"
    else:
        text += f"₿ BTC: {btc}\n"

    # ETH
    eth = format_crypto(cache['eth'])
    eth_old = p.get('eth')
    if eth_old:
        ch = pct(cache['eth'], eth_old)
        if ch > 0:
            text += f"Ξ ETH: {eth} (+{ch:.2f}%) 🟢\n"
        elif ch < 0:
            text += f"Ξ ETH: {eth} ({ch:.2f}%) 🔴\n"
        else:
            text += f"Ξ ETH: {eth}\n"
    else:
        text += f"Ξ ETH: {eth}\n"

    # TON
    ton = format_crypto(cache['ton'])
    ton_old = p.get('ton')
    if ton_old:
        ch = pct(cache['ton'], ton_old)
        if ch > 0:
            text += f"▽ TON: {ton} (+{ch:.2f}%) 🟢\n"
        elif ch < 0:
            text += f"▽ TON: {ton} ({ch:.2f}%) 🔴\n"
        else:
            text += f"▽ TON: {ton}\n"
    else:
        text += f"▽ TON: {ton}\n"

    text += "\n"

    # RUB
    rub = format_fiat(cache['rub'])
    rub_old = p.get('rub')
    if rub_old:
        ch = pct(cache['rub'], rub_old)
        if ch > 0:
            text += f"USD→RUB: {rub} ₽ (+{ch:.2f}%) 🟢\n"
        elif ch < 0:
            text += f"USD→RUB: {rub} ₽ ({ch:.2f}%) 🔴\n"
        else:
            text += f"USD→RUB: {rub} ₽\n"
    else:
        text += f"USD→RUB: {rub} ₽\n"

    # CNY
    cny = format_fiat(cache['cny'])
    cny_old = p.get('cny')
    if cny_old:
        ch = pct(cache['cny'], cny_old)
        if ch > 0:
            text += f"USD→CNY: {cny} ¥ (+{ch:.2f}%) 🟢\n"
        elif ch < 0:
            text += f"USD→CNY: {cny} ¥ ({ch:.2f}%) 🔴\n"
        else:
            text += f"USD→CNY: {cny} ¥\n"
    else:
        text += f"USD→CNY: {cny} ¥\n"

    text += "\n📌 <a href='https://t.me/send?start=r-x4zoa'>@CryptoBot</a>"
    return text

# ---------- TOP TEXT ----------
def build_top():
    movers = get_top_movers()

    if not movers:
        return "🚀 TOP MOVERS (1h)\n\nНет данных"

    text = "🚀 TOP MOVERS (1h)\n\n"

    for m in movers:
        ch = m["change"]
        icon = "🟢" if ch > 0 else "🔴"
        sign = "+" if ch > 0 else ""
        text += f"{m['symbol']} {sign}{ch:.2f}% {icon}\n"

    text += "\n📌 @bi11ionaire"
    return text

# ---------- LOOP ----------
async def updater():
    global cache, prev_cache
    logging.info("UPDATER started")

    # Первый запуск
    data = fetch_rates()
    if data:
        cache = data
        logging.info(f"Initial cache: {cache}")

    while True:
        await asyncio.sleep(300)
        data = fetch_rates()
        if data:
            prev_cache = cache.copy() if cache else data
            cache = data
            logging.info("Cache updated")

async def market_poster():
    global last_market_post
    logging.info("MARKET POSTER started")

    # Ждём первый кэш
    while not cache:
        await asyncio.sleep(1)

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
                    logging.info("Market post sent to channel")
                except Exception as e:
                    logging.error(f"Market post error: {e}")

        await asyncio.sleep(300)

async def top_poster():
    global last_top_post
    logging.info("TOP POSTER started")

    while True:
        text = build_top()
        if text != last_top_post:
            try:
                await bot.send_animation(
                    CHANNEL_ID,
                    TOP_GIF_ID,
                    caption=text,
                    parse_mode="HTML"
                )
                last_top_post = text
                logging.info("Top post with GIF sent to channel")
            except Exception as e:
                logging.error(f"Top post with GIF error: {e}")
                try:
                    await bot.send_message(CHANNEL_ID, text, disable_web_page_preview=True)
                    last_top_post = text
                    logging.info("Top post sent as text")
                except:
                    pass

        await asyncio.sleep(3600)

# ---------- HANDLERS ----------
@dp.message_handler(commands=["start"])
async def start(m: types.Message):
    await m.answer("Choose:", reply_markup=keyboard)

@dp.message_handler(lambda m: m.text == "📊 Exchange rates")
async def rates(m: types.Message):
    logging.info(f"Exchange rates requested by {m.from_user.id}")
    await m.answer(
        build_text(),
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=inline_kb
    )

@dp.message_handler(lambda m: m.text == "🚀 TOP")
async def top(m: types.Message):
    logging.info(f"TOP requested by {m.from_user.id}")
    try:
        await m.answer_animation(
            TOP_GIF_ID,
            caption=build_top(),
            parse_mode="HTML"
        )
    except Exception as e:
        logging.error(f"TOP with GIF error: {e}")
        await m.answer(build_top(), disable_web_page_preview=True)

@dp.callback_query_handler(lambda c: c.data == "update")
async def update(c: types.CallbackQuery):
    await c.answer()
    try:
        await c.message.edit_text(
            build_text(),
            parse_mode="HTML",
            reply_markup=inline_kb,
            disable_web_page_preview=True
        )
    except Exception as e:
        if "message is not modified" not in str(e).lower():
            logging.error(f"Update error: {e}")

# ---------- START ----------
async def on_startup(_):
    asyncio.create_task(updater())
    asyncio.create_task(market_poster())
    asyncio.create_task(top_poster())
    logging.info("Bot started")

# ---------- RUN ----------
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
