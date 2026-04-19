import yfinance as yf

stock = yf.Ticker("MSFT")
history = stock.history(period="2y")

if history.empty:
    print("Error: No data fetched. Try again.")
else:
    print(history)

    first_close = history["Close"].iloc[0]
    last_close = history["Close"].iloc[-1]

    change = ((last_close - first_close) / first_close) * 100

    print(f"Start: ${first_close:.2f}")
    print(f"End: ${last_close:.2f}")
    print(f"Change: {change:.2f}%")

    history["MA50"] = history["Close"].rolling(window=50).mean()
    history["MA200"] = history["Close"].rolling(window=200).mean()

    print(history[["Close", "MA50", "MA200"]].tail(10))

    latest = history.iloc[-1]

    if latest["MA50"] > latest["MA200"]:
        print("Signal: BUY 📈")
    else:
        print("Signal: SELL 📉")

    # Calculate RSI
    delta = history["Close"].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)

    avg_gain = gain.rolling(window=14).mean()
    avg_loss = loss.rolling(window=14).mean()

    rs = avg_gain / avg_loss
    history["RSI"] = 100 - (100 / (1 + rs))

    print(history[["Close", "RSI"]].tail(10))
    rsi_latest = history["RSI"].iloc[-1]

print("\n--- BOT DECISION ---")
if latest["MA50"] > latest["MA200"] and rsi_latest < 70:
    print("STRONG BUY 💚 - Trend is up and RSI is healthy")
elif latest["MA50"] > latest["MA200"] and rsi_latest >= 70:
    print("WEAK BUY ⚠️ - Trend is up but RSI is overbought")
elif latest["MA50"] < latest["MA200"] and rsi_latest <= 30:
    print("WEAK SELL ⚠️ - Trend is down but RSI is oversold, possible bounce")
else:
    print("STRONG SELL 🔴 - Trend is down and RSI confirms it")
# Backtesting
cash = 10000
shares = 0
buy_price = 0
trades = []

for i in range(200, len(history)):
    row = history.iloc[i]
    ma50 = row["MA50"]
    ma200 = row["MA200"]
    rsi = row["RSI"]
    price = row["Close"]
    date = history.index[i]

    if ma50 > ma200 and rsi < 75 and shares == 0:
        shares = int(cash / price)
        buy_price = price
        cash -= shares * price
        trades.append(f"BUY  {date.date()} | Price: ${price:.2f} | Shares: {shares}")

    elif ma50 < ma200 and shares > 0:
        cash += shares * price
        trades.append(f"SELL {date.date()} | Price: ${price:.2f} | Profit: ${(price - buy_price) * shares:.2f}")
        shares = 0

print("\n--- TRADE HISTORY ---")
for trade in trades:
    print(trade)

total = cash + (shares * history["Close"].iloc[-1])
print(f"\nFinal Portfolio Value: ${total:.2f}")
print(f"Return: {((total - 10000) / 10000) * 100:.2f}%")