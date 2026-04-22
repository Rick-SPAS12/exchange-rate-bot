import os
import asyncio
import requests
import logging
from datetime import datetime

from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ---------- TOKEN ----------
API_TOKEN = os.getenv("API_TOKEN") or "PASTE_YOUR_TOKEN_HERE"

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

CHANNEL_ID = "@bi11ionaire"

# ---------- CACHE ----------
cache = {}
prev_cache = {}
cache_lock = asyncio.Lock()

# ---------- ТОРГОВЫЕ ИНДИКАТОРЫ ----------
price_history = {
    "btc": [],
    "eth": [],
    "ton": []
}
history_lock = asyncio.Lock()

# ---------- UI ----------
inline_kb = InlineKeyboardMarkup().add(
    InlineKeyboardButton("🔄 Update", callback_data="update")
)

keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
keyboard.add("📊 Exchange rates", "🚀 TOP")

# ---------- REQUEST ----------
def safe_get(url, params=None):
    """Безопасный GET запрос"""
    try:
        r = requests.get(url, params=params, timeout=10)
        if r.status_code == 200:
            return r.json()
        else:
            logger.warning(f"Request failed with status {r.status_code}: {url}")
    except Exception as e:
        logger.error(f"Request error {url}: {e}")
    return None

# ---------- P2P ----------
def get_p2p_price(fiat):
    """Получение курса USDT через P2P Binance"""
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
        )
        
        if r.status_code != 200:
            logger.warning(f"P2P request failed for {fiat}: status {r.status_code}")
            return None
            
        data = r.json()
        
        # Проверка структуры ответа
        if isinstance(data, dict) and data.get("data") and len(data["data"]) > 0:
            price = data["data"][0].get("adv", {}).get("price")
            if price:
                return float(price)
                
    except Exception as e:
        logger.error(f"P2P error for {fiat}: {e}")
    
    return None

# ---------- MARKET ----------
def fetch_rates():
    """Получение курсов криптовалют и фиата"""
    try:
        # Получение курсов криптовалют
        crypto = safe_get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={
                "ids": "bitcoin,ethereum,the-open-network",
                "vs_currencies": "usd"
            }
        )

        if not crypto:
            logger.error("Failed to fetch crypto rates")
            return None

        # Получение P2P курсов
        rub_price = get_p2p_price("RUB")
        cny_price = get_p2p_price("CNY")
        
        # Использование кэша если P2P не ответил
        cached_rub = 90
        cached_cny = 7.2
        if cache:
            cached_rub = cache.get("rub", 90)
            cached_cny = cache.get("cny", 7.2)

        return {
            "btc": float(crypto.get("bitcoin", {}).get("usd", 0)),
            "eth": float(crypto.get("ethereum", {}).get("usd", 0)),
            "ton": float(crypto.get("the-open-network", {}).get("usd", 0)),
            "rub": rub_price if rub_price else cached_rub,
            "cny": cny_price if cny_price else cached_cny,
        }
    except Exception as e:
        logger.error(f"Error fetching rates: {e}")
        return None

# ---------- ТОРГОВЫЕ ИНДИКАТОРЫ ----------
def calculate_rsi(prices, period=14):
    """Расчет RSI (индекс относительной силы)"""
    if len(prices) < period + 1:
        return 50  # Нейтральное значение если данных мало
    
    gains = []
    losses = []
    
    for i in range(1, len(prices)):
        change = prices[i] - prices[i-1]
        if change > 0:
            gains.append(change)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(change))
    
    if len(gains) < period:
        return 50
    
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    
    if avg_loss == 0:
        return 100
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    
    return rsi

def calculate_ma(prices, period=7):
    """Расчет скользящей средней"""
    if len(prices) < period:
        return prices[-1] if prices else 0
    
    return sum(prices[-period:]) / period

def get_trading_signals(symbol, current_price):
    """Получение торговых сигналов на основе индикаторов"""
    global price_history
    
    signals = []
    
    # Добавляем текущую цену в историю
    if symbol in price_history:
        price_history[symbol].append(current_price)
        # Храним последние 50 значений
        if len(price_history[symbol]) > 50:
            price_history[symbol] = price_history[symbol][-50:]
    
    if len(price_history[symbol]) < 14:
        return signals  # Недостаточно данных
    
    # Расчет индикаторов
    rsi = calculate_rsi(price_history[symbol])
    ma7 = calculate_ma(price_history[symbol], 7)
    ma25 = calculate_ma(price_history[symbol], 25)
    prev_price = price_history[symbol][-2] if len(price_history[symbol]) > 1 else current_price
    
    # RSI сигналы
    if rsi > 70:
        signals.append("🔴 ПЕРЕКУПЛЕННОСТЬ (RSI > 70) - Возможна коррекция вниз")
    elif rsi < 30:
        signals.append("🟢 ПЕРЕПРОДАНОСТЬ (RSI < 30) - Возможен разворот вверх")
    
    # Сигналы по скользящим средним
    if ma7 > ma25 and price_history[symbol][-2] <= ma25 and current_price > ma25:
        signals.append("🟢 БЫЧИЙ СИГНАЛ - MA7 пересекла MA25 снизу вверх")
    elif ma7 < ma25 and price_history[symbol][-2] >= ma25 and current_price < ma25:
        signals.append("🔴 МЕДВЕЖИЙ СИГНАЛ - MA7 пересекла MA25 сверху вниз")
    
    # Моментные сигналы
    price_change = ((current_price - prev_price) / prev_price) * 100
    if price_change > 3:
        signals.append(f"⚡ СИЛЬНЫЙ РОСТ +{price_change:.1f}% за период")
    elif price_change < -3:
        signals.append(f"⚠️ СИЛЬНОЕ ПАДЕНИЕ {price_change:.1f}% за период")
    
    # Трендовые сигналы
    if len(price_history[symbol]) >= 5:
        last_5 = price_history[symbol][-5:]
        trend = "up" if last_5[-1] > last_5[0] else "down" if last_5[-1] < last_5[0] else "side"
        
        if trend == "up" and all(last_5[i] < last_5[i+1] for i in range(4)):
            signals.append("📈 УСТОЙЧИВЫЙ ВОСХОДЯЩИЙ ТРЕНД")
        elif trend == "down" and all(last_5[i] > last_5[i+1] for i in range(4)):
            signals.append("📉 УСТОЙЧИВЫЙ НИСХОДЯЩИЙ ТРЕНД")
    
    return signals

# ---------- TOP ----------
def get_top():
    """Получение топ-5 монет по изменению за час"""
    try:
        r = safe_get(
            "https://api.coingecko.com/api/v3/coins/markets",
            params={
                "vs_currency": "usd",
                "order": "market_cap_desc",
                "per_page": 50,
                "page": 1,
                "sparkline": "false",
                "price_change_percentage": "1h"
            }
        )

        if not isinstance(r, list):
            logger.warning("Top coins: response is not a list")
            return []

        movers = []
        for c in r:
            ch = c.get("price_change_percentage_1h_in_currency")
            
            if ch is None:
                ch = c.get("price_change_percentage_1h", 0)
            
            if ch is not None:
                symbol = c.get("symbol", "").upper()
                if symbol:
                    movers.append((symbol, float(ch)))

        movers.sort(key=lambda x: abs(x[1]), reverse=True)
        return movers[:5]

    except Exception as e:
        logger.error(f"Error getting top coins: {e}")
        return []

# ---------- FORMAT ----------
def pct(new_val, old_val):
    """Расчет процентного изменения"""
    if not old_val or old_val == 0:
        return 0
    return ((new_val - old_val) / old_val) * 100

def format_price(price):
    """Форматирование цены с разделителями"""
    if price >= 1000:
        return f"{price:,.0f}".replace(",", ".")
    elif price >= 1:
        return f"{price:,.2f}".replace(",", ".")
    else:
        return f"{price:.4f}"

def line(sym, name, value, old_val, suffix=""):
    """Форматирование строки с ценой и изменением"""
    if value is None:
        return f"{sym} {name}: N/A"

    if not old_val:
        formatted_price = format_price(value)
        return f"{sym} {name}: {formatted_price}{suffix}"

    change = pct(value, old_val)
    formatted_price = format_price(value)

    if change > 0:
        return f"{sym} {name}: {formatted_price}{suffix} (+{change:.2f}%) 🟢"
    elif change < 0:
        return f"{sym} {name}: {formatted_price}{suffix} ({change:.2f}%) 🔴"

    return f"{sym} {name}: {formatted_price}{suffix}"

# ---------- TEXT ----------
def build_text():
    """Формирование текста с рыночными данными и индикаторами"""
    if not cache:
        return "📊 Loading..."

    # Безопасное получение предыдущих значений
    prev_btc = prev_cache.get("btc") if prev_cache else None
    prev_eth = prev_cache.get("eth") if prev_cache else None
    prev_ton = prev_cache.get("ton") if prev_cache else None
    prev_rub = prev_cache.get("rub") if prev_cache else None
    prev_cny = prev_cache.get("cny") if prev_cache else None

    text = "<b>📊 LIVE MARKET</b>\n\n"
    text += f"{line('₿', 'BTC', cache.get('btc'), prev_btc)}\n"
    text += f"{line('Ξ', 'ETH', cache.get('eth'), prev_eth)}\n"
    text += f"{line('▽', 'TON', cache.get('ton'), prev_ton)}\n\n"
    text += f"{line('', 'USD→RUB', cache.get('rub'), prev_rub, ' ₽')}\n"
    text += f"{line('', 'USD→CNY', cache.get('cny'), prev_cny, ' ¥')}\n\n"
    
    # Добавляем торговые индикаторы для BTC и ETH
    text += "<b>📊 ТОРГОВЫЕ ИНДИКАТОРЫ</b>\n\n"
    
    # BTC индикаторы
    btc_signals = get_trading_signals("btc", cache.get('btc', 0))
    if btc_signals:
        text += "<b>₿ BTC Сигналы:</b>\n"
        for signal in btc_signals[:2]:  # Показываем не более 2 сигналов
            text += f"{signal}\n"
        text += "\n"
    
    # ETH индикаторы
    eth_signals = get_trading_signals("eth", cache.get('eth', 0))
    if eth_signals:
        text += "<b>Ξ ETH Сигналы:</b>\n"
        for signal in eth_signals[:2]:  # Показываем не более 2 сигналов
            text += f"{signal}\n"
        text += "\n"
    
    # TON индикаторы (опционально)
    ton_signals = get_trading_signals("ton", cache.get('ton', 0))
    if ton_signals:
        text += "<b>▽ TON Сигналы:</b>\n"
        for signal in ton_signals[:1]:  # Показываем не более 1 сигнала
            text += f"{signal}\n"
        text += "\n"
    
    text += "📌 <a href='https://t.me/send?start=r-x4zoa'>@CryptoBot</a>"
    return text

def build_top():
    """Формирование текста с топ-5 монет (с жирным шрифтом)"""
    data = get_top()

    if not data:
        return "<b>🚀 TOP MOVERS</b>\n\nНет данных для отображения"

    text = "<b>🚀 TOP MOVERS (1h)</b>\n\n"

    for sym, change in data:
        icon = "🟢" if change > 0 else "🔴"
        sign = "+" if change > 0 else ""
        text += f"{sym} {sign}{change:.2f}% {icon}\n"

    text += "\n📌 @bi11ionaire"
    return text

# ---------- BACKGROUND TASKS ----------
async def updater():
    """Фоновая задача обновления курсов"""
    global cache, prev_cache
    logger.info("Updater task started")
    
    while True:
        try:
            data = fetch_rates()
            if data:
                async with cache_lock:
                    prev_cache = cache.copy() if cache else data
                    cache = data
                logger.info(f"Rates updated: BTC={data.get('btc'):,.0f}, ETH={data.get('eth'):,.0f}")
            else:
                logger.warning("Failed to fetch rates, using cache")
        except Exception as e:
            logger.error(f"Updater error: {e}")
        
        await asyncio.sleep(300)  # 5 минут

async def market_poster():
    """Фоновая задача постинга рыночных данных в канал"""
    last_text = ""
    logger.info("Market poster task started")
    
    while True:
        try:
            if cache:
                async with cache_lock:
                    text = build_text()

                if text != last_text:
                    await bot.send_message(
                        CHANNEL_ID,
                        text,
                        parse_mode="HTML",
                        disable_web_page_preview=True
                    )
                    last_text = text
                    logger.info("Market update posted to channel")
        except Exception as e:
            logger.error(f"Market poster error: {e}")
        
        await asyncio.sleep(300)  # 5 минут

async def top_poster():
    """Фоновая задача постинга топ-монет в канал"""
    last_text = ""
    logger.info("Top poster task started")
    
    while True:
        try:
            text = build_top()

            if text != last_text:
                await bot.send_message(
                    CHANNEL_ID,
                    text,
                    parse_mode="HTML",
                    disable_web_page_preview=True
                )
                last_text = text
                logger.info("Top movers update posted to channel")
        except Exception as e:
            logger.error(f"Top poster error: {e}")
        
        await asyncio.sleep(3600)  # 1 час

# ---------- HANDLERS ----------
@dp.message_handler(commands=["start"])
async def start_command(message: types.Message):
    """Обработчик команды /start"""
    await message.answer(
        "🤖 Бот готов к работе!\n\n"
        "Выберите действие:",
        reply_markup=keyboard
    )

@dp.message_handler(lambda message: message.text and "Exchange" in message.text)
async def rates_command(message: types.Message):
    """Обработчик кнопки Exchange rates"""
    async with cache_lock:
        text = build_text()
    
    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=inline_kb,
        disable_web_page_preview=True
    )

@dp.message_handler(lambda message: message.text and "TOP" in message.text)
async def top_command(message: types.Message):
    """Обработчик кнопки TOP"""
    text = build_top()
    await message.answer(text, parse_mode="HTML")

@dp.callback_query_handler(lambda callback: callback.data == "update")
async def update_callback(callback: types.CallbackQuery):
    """Обработчик кнопки Update"""
    await callback.answer("🔄 Обновление...")
    
    async with cache_lock:
        text = build_text()
    
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=inline_kb,
        disable_web_page_preview=True
    )

# ---------- STARTUP ----------
async def on_startup(_):
    """Действия при запуске бота"""
    logger.info("Bot starting...")
    
    # Проверка доступа к каналу
    try:
        chat = await bot.get_chat(CHANNEL_ID)
        logger.info(f"✅ Connected to channel: {chat.title}")
    except Exception as e:
        logger.error(f"❌ Cannot access channel {CHANNEL_ID}: {e}")
        logger.warning("Make sure bot is admin in the channel")
    
    # Запуск фоновых задач
    asyncio.create_task(updater())
    asyncio.create_task(market_poster())
    asyncio.create_task(top_poster())
    
    logger.info("Bot is ready!")

# ---------- MAIN ----------
if __name__ == "__main__":
    if API_TOKEN == "PASTE_YOUR_TOKEN_HERE":
        logger.error("Please set your API_TOKEN!")
        exit(1)
    
    logger.info("Starting bot...")
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
