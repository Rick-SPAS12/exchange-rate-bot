import os
import asyncio
import requests

from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor

# ---------- TOKEN ----------
API_TOKEN = os.getenv("API_TOKEN")

if not API_TOKEN:
    raise ValueError("API_TOKEN is missing")

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# ---------- CHANNEL ----------
CHANNEL_ID = "@bi11ionaire"

# ---------- CACHE ----------
cache = None
prev_cache = None

# ---------- KEYBOARD ----------
inline_kb = InlineKeyboardMarkup().add(
    InlineKeyboardButton("🔄 Update", callback_data="update")
)

keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
keyboard.add("📊 Exchange rates")

# ---------- SAFE REQUEST ----------
def safe_get(url, params=None):
    try:
        r = requests.get(url, params=params, timeout=10)
        if r.status_code == 200:
            return r.json()
    except:
        pass
    return None

# ---------- P2P PRICE ----------
def get_p2p_price(fiat):
    try:
        url = "https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search"

        payload = {
            "asset": "USDT",
            "fiat": fiat,
            "merchantCheck": False,
            "page": 1,
            "rows": 1,
            "tradeType": "BUY"
        }

        r = requests.post(url, json=payload, timeout=10)
        data = r.json()

        if not data or "data" not in data or len(data["data"]) == 0:
            return None

        return float(data["data"][0]["adv"]["price"])

    except:
        return None

# ---------- FETCH DATA ----------
def fetch_rates():
    try:
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

        # fallback если P2P умер
        if rub is None:
            rub = 90
        if cny is None:
            cny = 7.2

        return {
            "btc": float(crypto["bitcoin"]["usd"]),
            "eth": float(crypto["ethereum"]["usd"]),
            "ton": float(crypto["the-open-network"]["usd"]),
            "rub": rub,
            "cny": cny,
        }

    except:
        return None

# ---------- UPDATE LOOP (2.5 min) ----------
async def live_updater():
    global cache, prev_cache

    while True:
        try:
            data = fetch_rates()

            if data:
                if cache:
                    prev_cache = cache.copy()
                cache = data

        except:
            pass

        await asyncio.sleep(150)  # 2.5 minutes

# ---------- % CHANGE ----------
def pct(new, old):
    if not old:
        return 0
    return ((new - old) / old) * 100

def line(name, value, old):
    if not old:
        return f"{name}: ${value:,.2f}"

    change = pct(value, old)
    arrow = "📈" if change >= 0 else "📉"
    return f"{name}: ${value:,.2f} ({change:+.2f}%) {arrow}"

# ---------- TEXT ----------
def build_text():
    if not cache:
        return "⏳ Loading market data..."

    return (
        "📊 LIVE MARKET\n\n"
        f"₿ {line('BTC', cache['btc'], prev_cache['btc'] if prev_cache else 0)}\n"
        f"Ξ {line('ETH', cache['eth'], prev_cache['eth'] if prev_cache else 0)}\n"
        f"💎 {line('TON', cache['ton'], prev_cache['ton'] if prev_cache else 0)}\n"
        f"💵 USD → RUB: {cache['rub']:,.2f} ₽\n"
        f"🇨🇳 USD → CNY: {cache['cny']:,.2f} ¥\n\n"
        '📌 <a href="https://t.me/send?start=r-x4zoa">@CryptoBot</a>'
    )

# ---------- HANDLERS ----------
@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    await message.answer("Choose option 👇", reply_markup=keyboard)

@dp.message_handler(lambda m: m.text == "📊 Exchange rates")
async def rates(message: types.Message):
    await message.answer(
        build_text(),
        reply_markup=inline_kb,
        parse_mode="HTML",
        disable_web_page_preview=True
    )

@dp.callback_query_handler(lambda c: c.data == "update")
async def update(callback: types.CallbackQuery):
    await callback.answer()

    await callback.message.edit_text(
        build_text(),
        reply_markup=inline_kb,
        parse_mode="HTML",
        disable_web_page_preview=True
    )

# ---------- CHANNEL POST (5 min) ----------
async def channel_poster():
    last_sent = ""

    while True:
        try:
            text = build_text()

            if cache and text != last_sent and "Loading" not in text:
                await bot.send_message(
                    CHANNEL_ID,
                    text,
                    parse_mode="HTML",
                    disable_web_page_preview=True
                )
                last_sent = text

        except:
            pass

        await asyncio.sleep(300)  # 5 minutes

# ---------- STARTUP ----------
async def on_startup(_):
    global cache, prev_cache

    # initial load
    for _ in range(5):
        data = fetch_rates()
        if data:
            cache = data
            prev_cache = data.copy()
            break
        await asyncio.sleep(2)

    asyncio.create_task(live_updater())
    asyncio.create_task(channel_poster())

# ---------- RUN ----------
if __name__ == "__main__":
    executor.start_polling(
        dp,
        skip_updates=True,
        on_startup=on_startup
    )
