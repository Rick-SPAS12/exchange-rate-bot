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

# ---------- P2P ----------
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

        r = requests.post(url, json=payload, timeout=10).json()

        if not r or "data" not in r or len(r["data"]) == 0:
            return None

        return float(r["data"][0]["adv"]["price"])

    except:
        return None

# ---------- FETCH ----------
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

# ---------- UPDATE LOOP ----------
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

        await asyncio.sleep(150)  # 2.5 min

# ---------- % CHANGE ----------
def pct(new, old):
    if not old or old == 0:
        return 0
    return ((new - old) / old) * 100

# ---------- FORMAT (3 STATES) ----------
def format_line(name, value, old):
    if not old:
        return f"{name}: {value:.2f} ⚪ (0.00%)"

    change = pct(value, old)

    if abs(change) < 0.05:
        icon = "⚪"
        sign = ""
    elif change > 0:
        icon = "🟢"
        sign = "+"
    else:
        icon = "🔴"
        sign = ""

    return f"{name}: {value:.2f} {icon} ({sign}{change:.2f}%)"

# ---------- TEXT ----------
def build_text():
    if not cache:
        return "⏳ Loading market data..."

    return (
        "📊 LIVE MARKET\n\n"
        f"₿ {format_line('BTC', cache['btc'], prev_cache['btc'] if prev_cache else 0)}\n"
        f"Ξ {format_line('ETH', cache['eth'], prev_cache['eth'] if prev_cache else 0)}\n"
        f"▽{format_line('TON', cache['ton'], prev_cache['ton'] if prev_cache else 0)}\n\n"
        f"💵 {format_line('USD→RUB', cache['rub'], prev_cache['rub'] if prev_cache else 0)} ₽\n"
        f"🇨🇳 {format_line('USD→CNY', cache['cny'], prev_cache['cny'] if prev_cache else 0)} ¥\n\n"
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

# ---------- CHANNEL ----------
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

        await asyncio.sleep(300)  # 5 min

# ---------- STARTUP ----------
async def on_startup(_):
    global cache, prev_cache

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
