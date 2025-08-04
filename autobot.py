import ccxt
import requests
import time
import json
import pandas as pd
import ta
import os

API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")

exchange = ccxt.binance({
    'apiKey': API_KEY,
    'secret': API_SECRET,
    'enableRateLimit': True
})

symbol_prefix = "/USDT"
max_positions = 3
capital_fraction = 0.10
rsi_threshold = 30
take_profit = 1.05
stop_loss = 0.97
positions_file = "positions.json"

def load_positions():
    try:
        with open(positions_file, "r") as f:
            return json.load(f)
    except:
        return {}

def save_positions(positions):
    with open(positions_file, "w") as f:
        json.dump(positions, f, indent=4)

def get_top_symbols(limit=20):
    url = "https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=volume_desc&per_page=20&page=1"
    response = requests.get(url)
    data = response.json()
    return [coin['symbol'].upper() + symbol_prefix for coin in data if coin['symbol'].upper() + symbol_prefix in exchange.load_markets()]

def get_rsi(symbol):
    bars = exchange.fetch_ohlcv(symbol, timeframe='1h', limit=100)
    df = pd.DataFrame(bars, columns=["time", "open", "high", "low", "close", "volume"])
    df["rsi"] = ta.momentum.RSIIndicator(df["close"]).rsi()
    return df["rsi"].iloc[-1], df["close"].iloc[-1]

def run_bot():
    positions = load_positions()
    balance = exchange.fetch_balance()
    usdt_balance = balance['total']['USDT']
    trade_amount = usdt_balance * capital_fraction

    top_symbols = get_top_symbols()

    for symbol in top_symbols:
        if symbol in positions or len(positions) >= max_positions:
            continue
        try:
            rsi, price = get_rsi(symbol)
            if rsi < rsi_threshold:
                print(f"📉 BUY SIGNAL: {symbol} - RSI: {rsi:.2f}")
                amount = trade_amount / price
                order = exchange.create_market_buy_order(symbol, amount)
                positions[symbol] = {
                    "buy_price": price,
                    "amount": amount
                }
                save_positions(positions)
        except Exception as e:
            print(f"Error analyzing {symbol}: {e}")

    for symbol in list(positions.keys()):
        try:
            ticker = exchange.fetch_ticker(symbol)
            current_price = ticker['last']
            entry = positions[symbol]
            buy_price = entry["buy_price"]

            if current_price >= buy_price * take_profit or current_price <= buy_price * stop_loss:
                print(f"💰 SELLING: {symbol} at {current_price}")
                exchange.create_market_sell_order(symbol, entry["amount"])
                del positions[symbol]
                save_positions(positions)
        except Exception as e:
            print(f"Error checking sell for {symbol}: {e}")

while True:
    print("🔁 Running trading cycle...")
    run_bot()
    print("⏳ Waiting 15 minutes...\n")
    time.sleep(900)
