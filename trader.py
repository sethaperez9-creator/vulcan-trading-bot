import yfinance as yf
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
import json
import os
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

PORTFOLIO_FILE = "portfolio.json"
WATCHLIST_FILE = "watchlist.json"
ALERTS_FILE = "alerts.json"
SETTINGS_FILE = "settings.json"

def load_watchlist():
    if os.path.exists(WATCHLIST_FILE):
        with open(WATCHLIST_FILE, "r") as f:
            return json.load(f)
    return ["SPY", "BRK-B", "AMC", "NVDA", "AAPL"]

def save_watchlist(watchlist):
    with open(WATCHLIST_FILE, "w") as f:
        json.dump(watchlist, f)

def load_portfolio():
    if os.path.exists(PORTFOLIO_FILE):
        with open(PORTFOLIO_FILE, "r") as f:
            return json.load(f)
    return {"cash": 10000, "positions": {}, "trades": []}

def save_portfolio(portfolio):
    with open(PORTFOLIO_FILE, "w") as f:
        json.dump(portfolio, f)

def load_alerts():
    if os.path.exists(ALERTS_FILE):
        with open(ALERTS_FILE, "r") as f:
            return json.load(f)
    return []

def save_alerts(alerts):
    with open(ALERTS_FILE, "w") as f:
        json.dump(alerts, f)

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r") as f:
            return json.load(f)
    return {"email": "", "gmail_user": "", "gmail_pass": ""}

def send_alert_email(alert, settings):
    if not settings["email"] or not settings["gmail_user"] or not settings["gmail_pass"]:
        return
    try:
        msg = MIMEMultipart()
        msg["From"] = settings["gmail_user"]
        msg["To"] = settings["email"]
        msg["Subject"] = f"⚡ Vulcan Alert — {alert['ticker']} hit ${alert['current_price']}"
        body = f"""
Vulcan Price Alert Triggered!

Stock: {alert['ticker']}
Target: ${alert['target']} ({alert['direction']})
Current Price: ${alert['current_price']}

— Vulcan Trading Bot
        """
        msg.attach(MIMEText(body, "plain"))
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(settings["gmail_user"], settings["gmail_pass"])
        server.send_message(msg)
        server.quit()
    except Exception as e:
        print(f"Email error: {e}")

def check_alerts():
    alerts = load_alerts()
    triggered = []
    remaining = []
    for alert in alerts:
        ticker = alert["ticker"]
        target = alert["target"]
        direction = alert["direction"]
        try:
            price = yf.Ticker(ticker).history(period="1d")["Close"].iloc[-1]
            price = round(price, 2)
            if direction == "above" and price >= target:
                triggered.append({**alert, "current_price": price})
            elif direction == "below" and price <= target:
                triggered.append({**alert, "current_price": price})
            else:
                remaining.append(alert)
        except:
            remaining.append(alert)
    save_alerts(remaining)
    return triggered

def analyze_stock(ticker):
    stock = yf.Ticker(ticker)
    history = stock.history(period="2y")

    if history.empty:
        print(f"{ticker}: No data found, skipping.")
        return None

    history["MA50"] = history["Close"].rolling(window=50).mean()
    history["MA200"] = history["Close"].rolling(window=200).mean()

    delta = history["Close"].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(window=14).mean()
    avg_loss = loss.rolling(window=14).mean()
    rs = avg_gain / avg_loss
    history["RSI"] = 100 - (100 / (1 + rs))
    history["Target"] = (history["Close"].shift(-1) > history["Close"]).astype(int)
    history.dropna(inplace=True)

    if len(history) < 50:
        print(f"{ticker}: Not enough data, skipping.")
        return None

    features = ["Close", "MA50", "MA200", "RSI"]
    X = history[features]
    y = history["Target"]

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)

    latest_row = history[features].iloc[-1]
    latest = pd.DataFrame([latest_row], columns=features)
    prediction = model.predict(latest)[0]

    rsi = round(history["RSI"].iloc[-1], 2)
    ma50 = round(history["MA50"].iloc[-1], 2)
    ma200 = round(history["MA200"].iloc[-1], 2)

    rsi_strength = rsi > 80 or rsi < 20
    rsi_moderate = (70 < rsi <= 80) or (20 <= rsi < 30)
    ma_gap = abs(ma50 - ma200) / ma200 * 100

    if rsi_strength and ma_gap > 5:
        confidence = "High"
    elif rsi_moderate or ma_gap > 2:
        confidence = "Medium"
    else:
        confidence = "Low"

    return {
        "ticker": ticker,
        "price": round(history["Close"].iloc[-1], 2),
        "rsi": rsi,
        "ma50": ma50,
        "ma200": ma200,
        "prediction": int(prediction),
        "confidence": confidence
    }

def get_chart_data(ticker):
    stock = yf.Ticker(ticker)
    history = stock.history(period="1y")
    history["MA50"] = history["Close"].rolling(window=50).mean()
    history["MA200"] = history["Close"].rolling(window=200).mean()

    # Only drop rows where MA50 is NaN, keep last 6 months
    history = history.dropna(subset=["MA50"])
    history = history.tail(126)  # ~6 months of trading days

    dates = [str(d.date()) for d in history.index]
    closes = history["Close"].round(2).tolist()
    ma50 = history["MA50"].round(2).tolist()
    ma200 = [round(x, 2) if str(x) != 'nan' else None for x in history["MA200"].tolist()]

    return {"dates": dates, "closes": closes, "ma50": ma50, "ma200": ma200}
    stock = yf.Ticker(ticker)
    history = stock.history(period="6mo")
    history["MA50"] = history["Close"].rolling(window=50).mean()
    history["MA200"] = history["Close"].rolling(window=200).mean()
    history.dropna(inplace=True)

    dates = [str(d.date()) for d in history.index]
    closes = history["Close"].round(2).tolist()
    ma50 = history["MA50"].round(2).tolist()
    ma200 = history["MA200"].round(2).tolist()

    return {"dates": dates, "closes": closes, "ma50": ma50, "ma200": ma200}

def run_bot():
    portfolio = load_portfolio()
    date = datetime.now().strftime("%Y-%m-%d")
    WATCHLIST = load_watchlist()

    print(f"\n{'='*50}")
    print(f"Running bot — {date}")
    print(f"Cash: ${portfolio['cash']:.2f}")
    print(f"{'='*50}")

    for ticker in WATCHLIST:
        print(f"\nAnalyzing {ticker}...")
        data = analyze_stock(ticker)

        if data is None:
            continue

        price = data["price"]
        prediction = data["prediction"]
        position = portfolio["positions"].get(ticker, {"shares": 0, "buy_price": 0})

        print(f"Price: ${price} | RSI: {data['rsi']} | Prediction: {'UP 📈' if prediction == 1 else 'DOWN 📉'} | Confidence: {data['confidence']}")

        if prediction == 1 and position["shares"] == 0 and portfolio["cash"] > price:
            allocation = portfolio["cash"] * 0.2
            shares = int(allocation / price)
            if shares > 0:
                cost = shares * price
                portfolio["cash"] -= cost
                portfolio["positions"][ticker] = {"shares": shares, "buy_price": price}
                trade = f"BUY {ticker} {date} | Price: ${price} | Shares: {shares} | Cost: ${cost:.2f}"
                portfolio["trades"].append(trade)
                print(f"Action: {trade}")

        elif prediction == 0 and position["shares"] > 0:
            revenue = position["shares"] * price
            profit = (price - position["buy_price"]) * position["shares"]
            portfolio["cash"] += revenue
            portfolio["positions"][ticker] = {"shares": 0, "buy_price": 0}
            trade = f"SELL {ticker} {date} | Price: ${price} | Profit: ${profit:.2f}"
            portfolio["trades"].append(trade)
            print(f"Action: {trade}")

        else:
            print(f"Action: HOLD")

    total = portfolio["cash"]
    for ticker, pos in portfolio["positions"].items():
        if pos["shares"] > 0:
            data = analyze_stock(ticker)
            if data:
                total += pos["shares"] * data["price"]

    print(f"\n{'='*50}")
    print(f"Portfolio Value: ${total:.2f}")
    print(f"Return: {((total - 10000) / 10000) * 100:.2f}%")
    print(f"{'='*50}")

    save_portfolio(portfolio)
    print("\nPortfolio saved.")

if __name__ == "__main__":
    run_bot()
    