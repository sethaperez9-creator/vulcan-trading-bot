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

WATCHLIST_FILE = "watchlist.json"
ALERTS_FILE = "alerts.json"
SETTINGS_FILE = "settings.json"
REGISTRY_FILE = "registry.json"
PORTFOLIOS_DIR = "portfolios"

def ensure_dirs():
    os.makedirs(PORTFOLIOS_DIR, exist_ok=True)

def load_watchlist():
    if os.path.exists(WATCHLIST_FILE):
        with open(WATCHLIST_FILE, "r") as f:
            return json.load(f)
    return ["SPY", "BRK-B", "AMC", "NVDA", "AAPL"]

def save_watchlist(watchlist):
    with open(WATCHLIST_FILE, "w") as f:
        json.dump(watchlist, f)

def get_portfolio_path(username):
    ensure_dirs()
    return os.path.join(PORTFOLIOS_DIR, f"{username}.json")

def load_portfolio(username):
    path = get_portfolio_path(username)
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return {"cash": 10000, "starting_cash": 10000, "positions": {}, "trades": []}

def save_portfolio(username, portfolio):
    with open(get_portfolio_path(username), "w") as f:
        json.dump(portfolio, f)

def set_starting_cash(username, amount):
    portfolio = load_portfolio(username)
    portfolio["cash"] = amount
    portfolio["starting_cash"] = amount
    portfolio["positions"] = {}
    portfolio["trades"] = []
    save_portfolio(username, portfolio)

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
        msg["Subject"] = f"Vulcan Alert — {alert['ticker']} hit ${alert['current_price']}"
        msg.attach(MIMEText(f"Alert triggered!\n\nStock: {alert['ticker']}\nTarget: ${alert['target']} ({alert['direction']})\nCurrent: ${alert['current_price']}", "plain"))
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(settings["gmail_user"], settings["gmail_pass"])
        server.send_message(msg)
        server.quit()
    except Exception as e:
        print(f"Email error: {e}")

def check_alerts():
    alerts = load_alerts()
    triggered, remaining = [], []
    for alert in alerts:
        try:
            price = round(yf.Ticker(alert["ticker"]).history(period="1d")["Close"].iloc[-1], 2)
            if (alert["direction"] == "above" and price >= alert["target"]) or \
               (alert["direction"] == "below" and price <= alert["target"]):
                triggered.append({**alert, "current_price": price})
            else:
                remaining.append(alert)
        except:
            remaining.append(alert)
    save_alerts(remaining)
    return triggered

def load_registry():
    if os.path.exists(REGISTRY_FILE):
        with open(REGISTRY_FILE, "r") as f:
            return json.load(f)
    return {}

def save_registry(registry):
    with open(REGISTRY_FILE, "w") as f:
        json.dump(registry, f)

def update_registry(username, ticker, shares, buy_price, action="add"):
    registry = load_registry()
    if ticker not in registry:
        registry[ticker] = {"total_shares": 0, "holders": {}}
    if action == "add":
        registry[ticker]["holders"][username] = {"shares": shares, "buy_price": buy_price, "added": datetime.now().isoformat()}
    elif action == "remove":
        registry[ticker]["holders"].pop(username, None)
    registry[ticker]["total_shares"] = sum(v["shares"] for v in registry[ticker]["holders"].values())
    if not registry[ticker]["holders"]:
        del registry[ticker]
    save_registry(registry)

def get_registry_with_flags():
    registry = load_registry()
    result = []
    for ticker, data in registry.items():
        try:
            info = yf.Ticker(ticker).info
            float_shares = info.get("floatShares") or info.get("sharesOutstanding") or 0
            community_shares = data["total_shares"]
            holders = len(data["holders"])
            flag, flag_reason = False, ""
            if float_shares > 0:
                pct = (community_shares / float_shares) * 100
                if pct > 0.01:
                    flag = True
                    flag_reason = f"Community holds {pct:.4f}% of float"
            share_counts = [v["shares"] for v in data["holders"].values()]
            if len(share_counts) > 2 and len(share_counts) != len(set(share_counts)):
                flag = True
                flag_reason = "Duplicate share counts detected"
            result.append({"ticker": ticker, "community_shares": community_shares, "float_shares": float_shares, "holders": holders, "flagged": flag, "flag_reason": flag_reason})
        except:
            result.append({"ticker": ticker, "community_shares": data["total_shares"], "float_shares": 0, "holders": len(data["holders"]), "flagged": False, "flag_reason": ""})
    return result

def analyze_stock(ticker):
    try:
        stock = yf.Ticker(ticker)
        history = stock.history(period="2y")
        if history.empty or len(history) < 50:
            return None
        history["MA20"] = history["Close"].rolling(window=20).mean()
        history["MA50"] = history["Close"].rolling(window=50).mean()
        history["MA200"] = history["Close"].rolling(window=200).mean()
        delta = history["Close"].diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        rs = gain.rolling(window=14).mean() / loss.rolling(window=14).mean()
        history["RSI"] = 100 - (100 / (1 + rs))
        ema12 = history["Close"].ewm(span=12).mean()
        ema26 = history["Close"].ewm(span=26).mean()
        history["MACD"] = ema12 - ema26
        history["Signal"] = history["MACD"].ewm(span=9).mean()
        history["Target"] = (history["Close"].shift(-1) > history["Close"]).astype(int)
        history.dropna(inplace=True)
        features = ["Close", "MA20", "MA50", "MA200", "RSI", "MACD", "Signal"]
        X, y = history[features], history["Target"]
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        model = RandomForestClassifier(n_estimators=100, random_state=42)
        model.fit(X_train, y_train)
        latest = pd.DataFrame([history[features].iloc[-1]], columns=features)
        prediction = model.predict(latest)[0]
        proba = float(model.predict_proba(latest)[0][1])
        rsi = round(history["RSI"].iloc[-1], 2)
        ma20 = round(history["MA20"].iloc[-1], 2)
        ma50 = round(history["MA50"].iloc[-1], 2)
        ma200 = round(history["MA200"].iloc[-1], 2)
        macd = round(history["MACD"].iloc[-1], 4)
        signal_line = round(history["Signal"].iloc[-1], 4)
        ma_gap = abs(ma50 - ma200) / ma200 * 100
        score = 0
        if proba > 0.65: score += 2
        elif proba > 0.55: score += 1
        if rsi < 35: score += 2
        elif rsi < 45: score += 1
        if ma50 > ma200: score += 1
        if macd > signal_line: score += 1
        if ma_gap > 3: score += 1
        confidence = "High" if score >= 5 else "Medium" if score >= 3 else "Low"
        prev_close = round(history["Close"].iloc[-2], 2)
        current_price = round(history["Close"].iloc[-1], 2)
        change_pct = round(((current_price - prev_close) / prev_close) * 100, 2)
        return {
            "ticker": ticker, "price": current_price, "prev_close": prev_close, "change_pct": change_pct,
            "rsi": rsi, "ma20": ma20, "ma50": ma50, "ma200": ma200, "macd": macd, "signal_line": signal_line,
            "prediction": int(prediction), "proba": round(proba, 3), "confidence": confidence
        }
    except Exception as e:
        print(f"Error analyzing {ticker}: {e}")
        return None

def get_chart_data(ticker):
    import math
    stock = yf.Ticker(ticker)
    history = stock.history(period="1y")
    history["MA20"] = history["Close"].rolling(window=20).mean()
    history["MA50"] = history["Close"].rolling(window=50).mean()
    history["MA200"] = history["Close"].rolling(window=200).mean()
    history = history.dropna(subset=["MA20"]).tail(126)

    def safe(val):
        try:
            v = float(val)
            return None if math.isnan(v) else round(v, 2)
        except: return None

    candles = [{"time": str(ts.date()), "open": safe(row["Open"]), "high": safe(row["High"]),
                "low": safe(row["Low"]), "close": safe(row["Close"]), "volume": int(row["Volume"])}
               for ts, row in history.iterrows()]
    ma20 = [{"time": str(ts.date()), "value": safe(row["MA20"])} for ts, row in history.iterrows() if safe(row["MA20"])]
    ma50 = [{"time": str(ts.date()), "value": safe(row["MA50"])} for ts, row in history.iterrows() if safe(row["MA50"])]
    ma200 = [{"time": str(ts.date()), "value": safe(row["MA200"])} for ts, row in history.iterrows() if safe(row["MA200"])]
    volumes = [{"time": str(ts.date()), "value": int(row["Volume"]),
                "color": "rgba(99,102,241,0.5)" if row["Close"] >= row["Open"] else "rgba(139,92,246,0.35)"}
               for ts, row in history.iterrows()]
    return {"candles": candles, "ma20": ma20, "ma50": ma50, "ma200": ma200, "volumes": volumes}

def run_bot(username):
    portfolio = load_portfolio(username)
    watchlist = load_watchlist()
    date = datetime.now().strftime("%Y-%m-%d %H:%M")
    for ticker in watchlist:
        data = analyze_stock(ticker)
        if data is None: continue
        price, prediction, proba, confidence = data["price"], data["prediction"], data["proba"], data["confidence"]
        position = portfolio["positions"].get(ticker, {"shares": 0, "buy_price": 0})
        should_buy = prediction == 1 and proba > 0.52 and position["shares"] == 0 and portfolio["cash"] > price * 5
        should_sell = position["shares"] > 0 and (prediction == 0 or data["rsi"] > 75 or proba < 0.45)
        if should_buy:
            alloc_pct = 0.30 if confidence == "High" else 0.20 if confidence == "Medium" else 0.12
            shares = int(portfolio["cash"] * alloc_pct / price)
            if shares > 0:
                cost = round(shares * price, 2)
                portfolio["cash"] = round(portfolio["cash"] - cost, 2)
                portfolio["positions"][ticker] = {"shares": shares, "buy_price": price}
                portfolio["trades"].append({"action": "BUY", "ticker": ticker, "date": date, "price": price, "shares": shares, "total": cost, "confidence": confidence, "proba": proba})
        elif should_sell:
            revenue = round(position["shares"] * price, 2)
            profit = round((price - position["buy_price"]) * position["shares"], 2)
            portfolio["cash"] = round(portfolio["cash"] + revenue, 2)
            portfolio["positions"][ticker] = {"shares": 0, "buy_price": 0}
            portfolio["trades"].append({"action": "SELL", "ticker": ticker, "date": date, "price": price, "shares": position["shares"], "total": revenue, "profit": profit, "proba": proba})
    save_portfolio(username, portfolio)
    return portfolio