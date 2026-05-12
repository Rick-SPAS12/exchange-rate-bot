import os
import asyncio
import requests
import logging

from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor

logging.basicConfig(level=logging.INFO)

# ---------- CONFIG ----------
API_TOKEN = os.getenv("API_TOKEN")
CHANNEL_ID = "@DataB8"
GIF_ID = "CgACAgIAAxkBAAIFo2nouVA6zP0KFKpM0KnvY_KFODitAALumgACuo15SoosersvVltBOwQ"

UPDATE_INTERVAL = 120   # обновление данных
MARKET_INTERVAL = 300   # пост рынка
TOP_INTERVAL = 3600     # пост топа

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

state = {
    "cache": {"btc": 0, "eth": 0, "ton": 0, "rub": 90.0, "cny": 7.0},
    "prev_cache": {"btc": 0, "eth": 0, "ton": 0, "rub": 90.0, "cny": 7.0},
    "top_movers_text": "Loading..."
}

# ---------- DATA ----------
def fetch_data():
    try:
        res = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids":"bitcoin,ethereum,the-open-network","vs_currencies":"usd"},
            timeout=10
        ).json()

        def p2p(fiat):
            try:
                r = requests.post(
                    "https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search",
                    json={"asset":"USDT","fiat":fiat,"page":1,"rows":1,"tradeType":"BUY"},
                    timeout=10
                ).json()
                return float(r["data"][0]["adv"]["price"])
            except:
                return None

        state["prev_cache"] = state["cache"].copy()

        state["cache"] = {
            "btc": float(res["bitcoin"]["usd"]),
            "eth": float(res["ethereum"]["usd"]),
            "ton": float(res["the-open-network"]["usd"]),
            "rub": p2p("RUB") or state["cache"]["rub"],
            "cny": p2p("CNY") or state["cache"]["cny"]
        }

        # TOP
        r_top = requests.get(
            "https://api.coingecko.com/api/v3/coins/markets",
            params={
                "vs_currency":"usd",
                "order":"market_cap_desc",
                "per_page":50,
                "page":1,
                "price_change_percentage":"1h"
            },
            timeout=10
        ).json()

        movers = []
        for c in r_top:
            ch = c.get("price_change_percentage_1h_in_currency")
            if ch is None:
                continue
            movers.append((c["symbol"].upper(), float(ch)))

        movers.sort(key=lambda x: abs(x[1]), reverse=True)

        text = "<b>🚀 TOP MOVERS (1h)</b>\n\n"
        for s, ch in movers[:5]:
            sign = "+" if ch > 0 else ""
            icon = "🟢" if ch > 0 else "🔴"
            text += f"<code>{s}</code> {sign}{ch:.2f}% {icon}\n"

        text += "\n📌 @bi11ionaire"
        state["top_movers_text"] = text

    except Exception as e:
        logging.error(f"Fetch error: {e}")

# ---------- FORMAT ----------
def fmt_crypto(v):
    return f"{v:,.0f}".replace(",", ".")

def fmt_fiat(v):
    return f"{v:.2f}"

def pct(n, o):
    if not o:
        return 0
    return (n - o) / o * 100

def line(name, val, old, suffix="", crypto=False):
    value = fmt_crypto(val) if crypto else fmt_fiat(val)
    ch = pct(val, old)

    if abs(ch) < 0.01:
        return f"{name}: {value}{suffix}"

    sign = "+" if ch > 0 else ""
    icon = "🟢" if ch > 0 else "🔴"

    return f"{name}: {value}{suffix} ({sign}{ch:.2f}%) {icon}"

# ---------- TEXT ----------
def build_market():
    c = state["cache"]
    p = state["prev_cache"]

    return (
        "<b>📊 LIVE MARKET</b>\n\n"
        f"₿ {line('BTC', c['btc'], p['btc'], crypto=True)}\n"
        f"Ξ {line('ETH', c['eth'], p['eth'], crypto=True)}\n"
        f"▽ {line('TON', c['ton'], p['ton'])}\n\n"
        f"{line('USD→RUB', c['rub'], p['rub'], ' ₽')}\n"
        f"{line('USD→CNY', c['cny'], p['cny'], ' ¥')}\n\n"
        '📌 <a href="https://t.me/send?start=r-x4zoa">@CryptoBot</a>'
    )

# ---------- HANDLERS ----------
@dp.message_handler(commands=['start'])
async def start(m: types.Message):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📊 Exchange rates", "🚀 TOP")
    await m.answer("Choose:", reply_markup=kb)

@dp.message_handler(lambda m: m.text and "Exchange" in m.text)
async def rates(m: types.Message):
    await m.answer(build_market(), parse_mode="HTML")

@dp.message_handler(lambda m: m.text and "TOP" in m.text)
async def top(m: types.Message):
    try:
        await m.answer_animation(GIF_ID, caption=state["top_movers_text"], parse_mode="HTML")
    except:
        await m.answer(state["top_movers_text"], parse_mode="HTML")

# ---------- LOOPS ----------
async def data_loop():
    while True:
        await asyncio.to_thread(fetch_data)
        await asyncio.sleep(UPDATE_INTERVAL)

async def market_loop():
    await asyncio.sleep(5)

    # первый пост сразу
    try:
        await bot.send_message(CHANNEL_ID, build_market(), parse_mode="HTML")
    except Exception as e:
        logging.error(e)

    while True:
        await asyncio.sleep(MARKET_INTERVAL)
        try:
            await bot.send_message(CHANNEL_ID, build_market(), parse_mode="HTML")
            logging.info("MARKET SENT")
        except Exception as e:
            logging.error(f"Market error: {e}")

async def top_loop():
    await asyncio.sleep(10)

    # первый пост сразу
    try:
        await bot.send_animation(CHANNEL_ID, GIF_ID, caption=state["top_movers_text"], parse_mode="HTML")
    except Exception as e:
        logging.error(e)

    while True:
        await asyncio.sleep(TOP_INTERVAL)
        try:
            await bot.send_animation(CHANNEL_ID, GIF_ID, caption=state["top_movers_text"], parse_mode="HTML")
            logging.info("TOP SENT")
        except Exception as e:
            logging.error(f"TOP error: {e}")

# ---------- START ----------
async def on_startup(_):
    await asyncio.to_thread(fetch_data)

    asyncio.create_task(data_loop())
    asyncio.create_task(market_loop())
    asyncio.create_task(top_loop())

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
