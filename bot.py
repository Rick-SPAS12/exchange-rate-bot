import os
import asyncio
import logging
import requests
import hashlib
from datetime import datetime
import random
import aiohttp
from collections import deque

from aiogram import Bot, Dispatcher, Router, types
from aiogram.filters import Command
from aiogram.types import InlineQueryResultArticle, InputTextMessageContent, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile
from aiogram.enums import ParseMode

logging.basicConfig(level=logging.INFO)

# ---------- CONFIG ----------
API_TOKEN = os.getenv("API_TOKEN")
CHANNEL_ID = "@DataB8"
GIF_ID = "CgACAgIAAxkBAAIFo2nouVA6zP0KFKpM0KnvY_KFODitAALumgACuo15SoosersvVltBOwQ"

bot = Bot(token=API_TOKEN)
dp = Dispatcher()
router = Router()

# Добавлен points в кэш
state = {
    "cache": {"btc": 78400.0, "eth": 2330.0, "ton": 1.32, "points": 1.04, "rub": 90.0, "cny": 6.82},
    "prev_cache": {"btc": 78400.0, "eth": 2330.0, "ton": 1.32, "points": 1.04, "rub": 90.0, "cny": 6.82},
    "top_text": "🚀 TOP MOVERS (1h)\n\nLoading..."
}

FALLBACK_PRICES = {"btc": 78400.0, "eth": 2330.0, "ton": 1.32, "points": 1.04}
FALLBACK_MOVERS = [
    {"s": "SOL", "c": 5.67, "price": 142.00},
    {"s": "BTC", "c": 2.34, "price": 78400.00},
    {"s": "DOGE", "c": -1.23, "price": 0.15},
    {"s": "ETH", "c": 1.12, "price": 2330.00},
    {"s": "TON", "c": -0.45, "price": 1.32}
]

# ---------- КЭШ ДЛЯ ГИФОК ----------
used_gifs = deque(maxlen=100)

# ---------- GIPHY FUNCTIONS (без изменений) ----------
async def get_random_cat_gif():
    """Получает качественную смешную гифку с котами через GIPHY API (ТОП-100)"""
    api_key = os.getenv("GIPHY_API_KEY")
    if not api_key:
        logging.error("GIPHY_API_KEY not found")
        return None

    params = {
        "api_key": api_key,
        "q": "fight cats",
        "rating": "pg-13",
        "limit": 100,
        "offset": 0,
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://api.giphy.com/v1/gifs/search", params=params, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    gifs = data.get('data', [])
                    if not gifs:
                        return None
                    
                    available_gifs = [g for g in gifs if g['id'] not in used_gifs]
                    if not available_gifs:
                        used_gifs.clear()
                        available_gifs = gifs
                    
                    random_gif = random.choice(available_gifs)
                    used_gifs.append(random_gif['id'])
                    gif_url = random_gif.get('images', {}).get('downsized_large', {}).get('url')
                    
                    if gif_url and gif_url.endswith('.gif'):
                        async with session.get(gif_url) as gif_response:
                            if gif_response.status == 200 and 'image/gif' in gif_response.headers.get('Content-Type', ''):
                                return BufferedInputFile(await gif_response.read(), filename="cat.gif")
    except Exception as e:
        logging.error(f"GIPHY error: {e}")

    return await get_fallback_gif()

async def get_fallback_gif():
    """Запасная гифка"""
    fallback_urls = [
        "https://media.giphy.com/media/QJvwBSGaoc4eI/giphy.gif",
        "https://media.giphy.com/media/VbnUQpnihPSIgIXuZv/giphy.gif",
        "https://media.giphy.com/media/5xtDarmwsuR9sDRObyU/giphy.gif",
    ]
    for url in fallback_urls:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        return BufferedInputFile(await response.read(), filename="fallback.gif")
        except Exception:
            continue
    return None

# ---------- FEAR & GREED INDEX (без изменений) ----------
def get_fear_greed():
    try:
        data = requests.get("https://api.alternative.me/fng/", timeout=10).json()
        if data and "data" in data:
            item = data["data"][0]
            value = int(item["value"])
            
            if value <= 25:
                emoji, sentiment = "😱", "Extreme Fear"
            elif value <= 45:
                emoji, sentiment = "😨", "Fear"
            elif value <= 55:
                emoji, sentiment = "😐", "Neutral"
            elif value <= 75:
                emoji, sentiment = "😊", "Greed"
            else:
                emoji, sentiment = "🤑", "Extreme Greed"
            
            return {
                "value": value,
                "classification": item["value_classification"],
                "sentiment": sentiment,
                "emoji": emoji,
                "timestamp": datetime.fromtimestamp(int(item["timestamp"])).strftime("%d %b %Y %H:%M")
            }
    except Exception as e:
        logging.error(f"Fear & Greed error: {e}")
    return None

def build_fear_greed_msg():
    fg = get_fear_greed()
    if not fg:
        return None
    return (
        f"<b>😨 CRYPTO FEAR & GREED INDEX</b>\n\n"
        f"{fg['emoji']} <b>Value:</b> {fg['value']}/100\n"
        f"<b>Sentiment:</b> {fg['sentiment']}\n"
        f"<b>Classification:</b> {fg['classification']}\n\n"
        f"🕐 <i>Updated: {fg['timestamp']} UTC</i>\n\n"
        f"📌 @DataB8"
    )

# ---------- POINTS FETCH (НОВАЯ ФУНКЦИЯ) ----------
async def fetch_points_price():
    """Получает цену Mintless Points через GeckoTerminal API"""
    network = "ton"
    token_address = "EQD6Z9DHc5Mx-8PI8I4BjGX0d2NhapaRAK12CgstweNoMint"
    url = f"https://api.geckoterminal.com/api/v2/networks/{network}/tokens/{token_address}"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=15) as response:
                if response.status == 200:
                    data = await response.json()
                    token_data = data.get('data', {})
                    attrs = token_data.get('attributes', {})
                    
                    price_usd = float(attrs.get('price_usd', 0))
                    if price_usd > 0:
                        logging.info(f"✅ Points: ${price_usd:.4f}")
                        return price_usd
                elif response.status == 429:
                    logging.warning("GeckoTerminal rate limit, waiting 60s...")
                    await asyncio.sleep(60)
                else:
                    logging.error(f"GeckoTerminal API error: {response.status}")
    except Exception as e:
        logging.error(f"Points fetch error: {e}")
    
    return None

# ---------- MARKET TEXT (ИСПРАВЛЕНО + POINTS) ----------
def build_market_text():
    """Текст сводки (без кнопки)"""
    c, p = state["cache"], state["prev_cache"]
    
    def line_crypto(name, val, old):
        if old == 0 or val == 0:
            return f"<b>{name}</b>: {val:,.2f}$"
        ch = ((val - old) / old * 100)
        if abs(ch) < 0.01:
            return f"<b>{name}</b>: {val:,.2f}$"
        sign, icon = ("+", "🟢") if ch > 0 else ("", "🔴")
        return f"<b>{name}</b>: {val:,.2f}$ ({sign}{ch:.2f}%)  {icon}"
    
    def line_fiat(name, val, old, symbol):
        if old == 0 or val == 0:
            return f"<b>{name}</b>: {val:.2f}{symbol}"
        ch = ((val - old) / old * 100)
        if abs(ch) < 0.01:
            return f"<b>{name}</b>: {val:.2f}{symbol}"
        sign, icon = ("+", "🟢") if ch > 0 else ("", "🔴")
        return f"<b>{name}</b>: {val:.2f}{symbol} ({sign}{ch:.2f}%)  {icon}"
    
    # Points с изменением
    points_val = c.get('points', 0)
    points_old = p.get('points', 0)
    
    if points_old == 0 or points_val == 0:
        points_line = f"⬩ <b>Points</b>: {points_val:.4f}$"
    else:
        ch = ((points_val - points_old) / points_old * 100)
        if abs(ch) < 0.01:
            points_line = f"⬩ <b>Points</b>: {points_val:.4f}$"
        else:
            sign, icon = ("+", "🟢") if ch > 0 else ("", "🔴")
            points_line = f"⬩ <b>Points</b>: {points_val:.4f}$ ({sign}{ch:.2f}%)  {icon}"
    
    return (
        "<b>📊 LIVE MARKET</b>\n\n"
        f"◈ {line_crypto('TON', c['ton'], p['ton'])}\n"
        f"₿  {line_crypto('BTC', c['btc'], p['btc'])}\n"
        f"Ξ  {line_crypto('ETH', c['eth'], p['eth'])}\n"
        f"{points_line}\n\n"
        f"{line_fiat('USD→RUB', c['rub'], p['rub'], '₽')}\n"
        f"{line_fiat('USD→CNY', c['cny'], p['cny'], '¥')}\n\n"
        '📌 <a href="https://t.me/send?start=r-x4zoa">@CryptoBot</a>'
    )
def build_market_msg():
    """Текст + кнопка SHARE (для бота)"""
    text = build_market_text()
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 SHARE", switch_inline_query="\\rate👆click📊")]
    ])
    return text, keyboard

# ---------- DATA LOGIC (ОБНОВЛЁН) ----------
async def async_fetch_all_data():
    """Асинхронная версия fetch_all_data"""
    global state
    state["prev_cache"] = state["cache"].copy()
    
    # Основные цены через CoinGecko (в отдельном потоке)
    try:
        res = await asyncio.to_thread(
            lambda: requests.get(
                "https://api.coingecko.com/api/v3/simple/price",
                params={"ids": "bitcoin,ethereum,the-open-network", "vs_currencies": "usd"},
                timeout=10
            ).json()
        )
        if res and "bitcoin" in res:
            state["cache"]["btc"] = float(res["bitcoin"].get("usd", FALLBACK_PRICES["btc"]))
            state["cache"]["eth"] = float(res["ethereum"].get("usd", FALLBACK_PRICES["eth"]))
            state["cache"]["ton"] = float(res["the-open-network"].get("usd", FALLBACK_PRICES["ton"]))
            logging.info(f"📊 Prices: BTC={state['cache']['btc']}, ETH={state['cache']['eth']}, TON={state['cache']['ton']}")
    except Exception as e:
        logging.warning(f"CoinGecko error: {e}")
    
    # Фиатные курсы
    for fiat in ["RUB", "CNY"]:
        try:
            r = await asyncio.to_thread(
                lambda f=fiat: requests.post(
                    "https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search",
                    json={"asset": "USDT", "fiat": f, "page": 1, "rows": 1, "tradeType": "BUY"},
                    timeout=10
                ).json()
            )
            if r.get("data") and len(r["data"]) > 0:
                state["cache"][fiat.lower()] = float(r["data"][0]["adv"]["price"])
                logging.info(f"💱 {fiat}: {state['cache'][fiat.lower()]}")
        except Exception as e:
            logging.warning(f"P2P {fiat} error: {e}")
    
    # Points цена (НОВОЕ)
    try:
        points_price = await fetch_points_price()
        if points_price:
            state["cache"]["points"] = points_price
            logging.info(f"⬩ Points updated: ${points_price:.4f}")
    except Exception as e:
        logging.warning(f"Points update error: {e}")
    
    # Top Movers
    try:
        top_res = await asyncio.to_thread(
            lambda: requests.get(
                "https://api.coingecko.com/api/v3/coins/markets",
                params={"vs_currency": "usd", "order": "market_cap_desc", "per_page": 50, "page": 1, "price_change_percentage": "1h"},
                timeout=10
            ).json()
        )
        movers = []
        if isinstance(top_res, list):
            for c in top_res:
                if not isinstance(c, dict):
                    continue
                ch = c.get("price_change_percentage_1h_in_currency")
                price = c.get("current_price")
                if ch is not None and price is not None:
                    movers.append({"s": c["symbol"].upper(), "c": float(ch), "price": float(price)})
        if not movers:
            movers = FALLBACK_MOVERS
        movers.sort(key=lambda x: abs(x["c"]), reverse=True)
        
        txt = "🚀 <b>TOP MOVERS (1h)</b>\n\n"
        for m in movers[:5]:
            arrow = "🔼" if m['c'] > 0 else "🔽"
            sign = "+" if m['c'] > 0 else ""
            price_str = f"{m['price']:.8f}".rstrip('0').rstrip('.') if m['price'] < 1 else f"{m['price']:,.2f}"
            txt += f"<b>{m['s']}</b>-{price_str}$ {sign}{m['c']:.2f}% {arrow}\n"
        txt += "\n📌 @DataB8"
        state["top_text"] = txt
        logging.info("✅ TOP MOVERS updated")
    except Exception as e:
        logging.error(f"Top movers error: {e}")

# ---------- HANDLERS (без изменений) ----------
@router.inline_query()
async def inline_handler(query: types.InlineQuery):
    if query.query.strip().startswith("\\rate"):
        text = build_market_text()
        result_id = hashlib.md5(text.encode()).hexdigest()
        await query.answer(results=[
            InlineQueryResultArticle(
                id=result_id,
                title="📊 LIVE MARKET",
                description="Send market summary",
                input_message_content=InputTextMessageContent(message_text=text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
            )
        ], cache_time=1)

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊Rates"), KeyboardButton(text="🚀Top Movers")],
            [KeyboardButton(text="😨Fear&Greed"), KeyboardButton(text="🎭Gif")]
        ],
        resize_keyboard=True
    )
    await message.answer("Select report:", reply_markup=kb)

@router.message(lambda m: m.text == "📊Rates")
async def btn_market(message: types.Message):
    text, keyboard = build_market_msg()
    await message.answer(text, parse_mode=ParseMode.HTML, disable_web_page_preview=True, reply_markup=keyboard)

@router.message(lambda m: m.text == "🚀Top Movers")
async def btn_top(message: types.Message):
    try:
        await message.answer_animation(GIF_ID, caption=state["top_text"], parse_mode=ParseMode.HTML)
    except Exception:
        await message.answer(state["top_text"], parse_mode=ParseMode.HTML)

@router.message(lambda m: m.text == "😨Fear&Greed")
async def btn_fear_greed(message: types.Message):
    await message.answer("📊 Fetching Crypto Fear & Greed Index...")
    text = build_fear_greed_msg()
    await message.answer(text if text else "❌ Failed to fetch Fear & Greed Index.", parse_mode=ParseMode.HTML, disable_web_page_preview=True)

@router.message(lambda m: m.text == "🎭Gif")
async def random_gif_handler(message: types.Message):
    waiting = await message.answer("🐱 Looking for a funny cat GIF...")
    gif = await get_random_cat_gif()
    if gif:
        await message.answer_animation(animation=gif, caption="🐱 Here's a funny cat GIF for you! 🐾\n\n📌 @DataB8", parse_mode=ParseMode.HTML)
    else:
        await message.answer("❌ Could not find a cat GIF. Please try again later!")
    await waiting.delete()

# ---------- LOOPS (ОБНОВЛЁН data_updater) ----------
async def data_updater():
    while True:
        await async_fetch_all_data()
        await asyncio.sleep(150)

async def channel_market_loop():
    await asyncio.sleep(30)
    while True:
        try:
            await bot.send_message(CHANNEL_ID, build_market_text(), parse_mode=ParseMode.HTML, disable_web_page_preview=True)
            logging.info(f"✅ MARKET post sent to {CHANNEL_ID}")
        except Exception as e:
            logging.error(f"MARKET error: {e}")
        await asyncio.sleep(300)

async def channel_top_loop():
    await asyncio.sleep(61)
    while True:
        try:
            await bot.send_animation(CHANNEL_ID, GIF_ID, caption=state["top_text"], parse_mode=ParseMode.HTML)
            logging.info(f"✅ TOP MOVERS post sent to {CHANNEL_ID}")
        except Exception as e:
            logging.error(f"TOP error: {e}")
        await asyncio.sleep(3600)

async def channel_fear_greed_loop():
    await asyncio.sleep(92)
    while True:
        try:
            text = build_fear_greed_msg()
            if text:
                await bot.send_message(CHANNEL_ID, text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
                logging.info(f"✅ FEAR & GREED post sent to {CHANNEL_ID}")
        except Exception as e:
            logging.error(f"FEAR & GREED error: {e}")
        await asyncio.sleep(43200)

async def channel_cat_gif_loop():
    await asyncio.sleep(121)
    while True:
        try:
            gif = await get_random_cat_gif()
            if gif:
                await bot.send_animation(CHANNEL_ID, animation=gif, caption="🐱 Random funny cat GIF for you! 🐾\n\n📌 @DataB8")
                logging.info(f"✅ CAT GIF post sent to {CHANNEL_ID}")
        except Exception as e:
            logging.error(f"CAT GIF error: {e}")
        await asyncio.sleep(86400)

# ---------- MAIN ----------
async def main():
    print("🚀 Starting bot...")
    await asyncio.sleep(3)
    await bot.delete_webhook(drop_pending_updates=True)
    await asyncio.sleep(1)
    
    await async_fetch_all_data()
    print("📊 Data loaded")
    
    asyncio.create_task(data_updater())
    asyncio.create_task(channel_market_loop())
    asyncio.create_task(channel_top_loop())
    asyncio.create_task(channel_fear_greed_loop())
    asyncio.create_task(channel_cat_gif_loop())
    
    dp.include_router(router)
    
    print("✅ Bot started on aiogram 3.x")
    print("📢 Auto posts to @DataB8")
    print("📊 - MARKET: every 5 minutes (with Points)")
    print("🚀 - TOP MOVERS: every 1 hour")
    print("😊 - FEAR & GREED: every 12 hours")
    print("🐱 - CAT GIF: every 24 hours")
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
