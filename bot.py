import os
import asyncio
import aiohttp
import logging

from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor

# ================= CONFIG =================
API_TOKEN = os.getenv("API_TOKEN")
CHANNEL_ID = "@bi11ionaire"

UPDATE_INTERVAL = 300
TOP_INTERVAL = 3600

GIF_ID = "CgACAgIAAxkBAAIFo2nouVA6zP0KFKpM0KnvY_KFODitAALumgACuo15SoosersvVltBOwQ"

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# ================= CACHE =================
cache = {}
prev_cache = {}

# ================= UI =================
keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
keyboard.add("📊 Exchange rates", "🚀 TOP MOVERS")

inline_kb = InlineKeyboardMarkup().add(
    InlineKeyboardButton("🔄 Update", callback_data="update")
)

# ================= ASYNC REQUESTS =================
async def async_get(url, params=None):
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, params=params, timeout=10) as resp:
                if resp.status == 200:
                    return await resp.json()
        except:
            pass
    return None


async def get_p2p_price(fiat):
    url = "https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search"
    payload = {
        "asset": "USDT",
        "fiat": fiat,
        "page": 1,
        "rows": 1,
        "tradeType": "BUY"
    }
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, json=payload, timeout=10) as resp:
                data = await resp.json()
                if data.get("data"):
                    return float(data["data"][0]["adv"]["price"])
        except:
            pass
    return None


async def fetch_rates():
    data = await async_get(
        "https://api.coingecko.com/api/v3/simple/price",
        {"ids": "bitcoin,ethereum,the-open-network", "vs_currencies": "usd"}
    )

    if not data:
        return None

    rub = await get_p2p_price("RUB")
    cny = await get_p2p_price("CNY")

    return {
        "btc": float(data["bitcoin"]["usd"]),
        "eth": float(data["ethereum"]["usd"]),
        "ton": float(data["the-open-network"]["usd"]),
        "rub": rub or cache.get("rub", 90),
        "cny": cny or cache.get("cny", 7.2),
    }


async def get_top():
    data = await async_get(
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


# ================= FORMAT =================
def pct(new, old):
    if not old:
        return 0
    return ((new - old) / old) * 100


def fmt_crypto(v):
    return f"{v:,.0f}".replace(",", ".")


def fmt_fiat(v):
    return f"{v:,.2f}".replace(",", ".")


def build_market():
    if not cache:
        return "📊 Loading..."

    prev = prev_cache or cache

    btc = fmt_crypto(cache["btc"])
    btc_old = prev.get("btc")
    if btc_old:
        ch = pct(cache["btc"], btc_old)
        btc_line = f"₿ BTC: {btc} (+{ch:.2f}%) 🟢" if ch > 0 else f"₿ BTC: {btc} ({ch:.2f}%) 🔴" if ch < 0 else f"₿ BTC: {btc}"
    else:
        btc_line = f"₿ BTC: {btc}"

    eth = fmt_crypto(cache["eth"])
    eth_old = prev.get("eth")
    if eth_old:
        ch = pct(cache["eth"], eth_old)
        eth_line = f"Ξ ETH: {eth} (+{ch:.2f}%) 🟢" if ch > 0 else f"Ξ ETH: {eth} ({ch:.2f}%) 🔴" if ch < 0 else f"Ξ ETH: {eth}"
    else:
        eth_line = f"Ξ ETH: {eth}"

    ton = fmt_crypto(cache["ton"])
    ton_old = prev.get("ton")
    if ton_old:
        ch = pct(cache["ton"], ton_old)
        ton_line = f"▽ TON: {ton} (+{ch:.2f}%) 🟢" if ch > 0 else f"▽ TON: {ton} ({ch:.2f}%) 🔴" if ch < 0 else f"▽ TON: {ton}"
    else:
        ton_line = f"▽ TON: {ton}"

    rub = fmt_fiat(cache["rub"])
    rub_old = prev.get("rub")
    if rub_old:
        ch = pct(cache["rub"], rub_old)
        rub_line = f"USD→RUB: {rub} ₽ (+{ch:.2f}%) 🟢" if ch > 0 else f"USD→RUB: {rub} ₽ ({ch:.2f}%) 🔴" if ch < 0 else f"USD→RUB: {rub} ₽"
    else:
        rub_line = f"USD→RUB: {rub} ₽"

    cny = fmt_fiat(cache["cny"])
    cny_old = prev.get("cny")
    if cny_old:
        ch = pct(cache["cny"], cny_old)
        cny_line = f"USD→CNY: {cny} ¥ (+{ch:.2f}%) 🟢" if ch > 0 else f"USD→CNY: {cny} ¥ ({ch:.2f}%) 🔴" if ch < 0 else f"USD→CNY: {cny} ¥"
    else:
        cny_line = f"USD→CNY: {cny} ¥"

    return (
        "<b>📊 LIVE MARKET</b>\n\n"
        f"{btc_line}\n"
        f"{eth_line}\n"
        f"{ton_line}\n\n"
        f"{rub_line}\n"
        f"{cny_line}\n\n"
        "📌 <a href='https://t.me/send?start=r-x4zoa'>@CryptoBot</a>"
    )


async def build_top():
    movers = await get_top()

    if not movers:
        return "<b>🚀 TOP MOVERS (1h)</b>\n\n⚠️ Нет данных"

    text = "<b>🚀 TOP MOVERS (1h)</b>\n\n"
    for s, ch in movers:
        sign = "+" if ch > 0 else ""
        icon = "🟢" if ch > 0 else "🔴"
        text += f"{s} {sign}{ch:.2f}% {icon}\n"
    return text


# ================= TASKS =================
async def updater():
    global cache, prev_cache
    while True:
        data = await fetch_rates()
        if data:
            if cache:
                prev_cache = cache.copy()
            cache = data
        await asyncio.sleep(UPDATE_INTERVAL)


async def market_post():
    while not cache:
        await asyncio.sleep(1)
    while True:
        try:
            await bot.send_message(CHANNEL_ID, build_market(), parse_mode="HTML")
        except Exception as e:
            logging.error(f"Market post: {e}")
        await asyncio.sleep(UPDATE_INTERVAL)


async def top_post():
    while True:
        try:
            caption = await build_top()
            await bot.send_animation(CHANNEL_ID, GIF_ID, caption=caption, parse_mode="HTML")
        except Exception as e:
            logging.error(f"Top post: {e}")
        await asyncio.sleep(TOP_INTERVAL)


# ================= HANDLERS =================
@dp.message_handler(commands=["start"])
async def start(m: types.Message):
    await m.answer("Выбери:", reply_markup=keyboard)


@dp.message_handler(lambda m: m.text == "📊 Exchange rates")
async def rates(m: types.Message):
    await m.answer(build_market(), parse_mode="HTML", reply_markup=inline_kb)


@dp.message_handler(lambda m: m.text == "🚀 TOP MOVERS")
async def top(m: types.Message):
    caption = await build_top()
    await m.answer_animation(GIF_ID, caption=caption, parse_mode="HTML")


@dp.callback_query_handler(lambda c: c.data == "update")
async def update(c: types.CallbackQuery):
    await c.answer()
    try:
        await c.message.edit_text(build_market(), parse_mode="HTML", reply_markup=inline_kb)
    except:
        pass


# ================= START =================
async def on_startup(_):
    data = await fetch_rates()
    if data:
        global cache
        cache = data
    asyncio.create_task(updater())
    asyncio.create_task(market_post())
    asyncio.create_task(top_post())


if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
