import yfinance as yf
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
import json
import os
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor
import smtplib
from email.mime.text import MIMEText
import time
import random

# --- CONFIGURATION ---
PORTFOLIO_FILE = "portfolio.json"
WATCHLIST_FILE = "watchlist.json"
ALERTS_FILE = "alerts.json"

# Institutional Universe (Our 'Hunting Ground')
INSTITUTIONAL_UNIVERSE = ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA", "AVGO", "COST", "NFLX", "AMD", "QCOM"]

# --- HELPER FUNCTIONS ---

def load_json(file, default):
    if os.path.exists(file):
        with open(file, "r") as f: return json.load(f)
    return default

def save_json(file, data):
    with open(file, "w") as f: json.dump(data, f, indent=4)

def send_email(subject, body):
    # Update these with your actual credentials or environment variables
    SENDER = "your-email@gmail.com"
    PASSWORD = "your-app-password"
    RECEIVER = "your-email@gmail.com"
    
    try:
        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = SENDER
        msg['To'] = RECEIVER
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(SENDER, PASSWORD)
            server.send_message(msg)
        print("📧 Email alert sent!")
    except Exception as e:
        print(f"❌ Email failed: {e}")

# --- ANALYSIS (Runs in Parallel) ---

def analyze_stock(ticker):
    try:
        stock = yf.Ticker(ticker)
        time.sleep(random.uniform(0.1, 0.3))
        df = stock.history(period="2y")
        if len(df) < 201: return None

        # Indicators
        df["MA50"] = df["Close"].rolling(window=50).mean()
        df["MA200"] = df["Close"].rolling(window=200).mean()
        delta = df["Close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / (loss + 1e-9)
        df["RSI"] = 100 - (100 / (1 + rs))

        # ML Training
        df["Target"] = (df["Close"].shift(-1) > df["Close"]).astype(int)
        df.dropna(inplace=True)
        X = df[["Close", "MA50", "MA200", "RSI"]]
        y = df["Target"]
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)
        
        model = RandomForestClassifier(n_estimators=100, random_state=42)
        model.fit(X_train, y_train)

        latest = X.iloc[[-1]]
        prediction = model.predict(latest)[0]
        prob = model.predict_proba(latest)[0][prediction]

        return {
            "ticker": ticker,
            "price": round(df["Close"].iloc[-1], 2),
            "prediction": int(prediction),
            "prob": round(prob, 4),
            "rsi": round(df["RSI"].iloc[-1], 2)
        }
    except: return None

# --- ENGINE ---

def run_bot():
    portfolio = load_json(PORTFOLIO_FILE, {"cash": 10000, "positions": {}, "trades": []})
    watchlist = load_json(WATCHLIST_FILE, ["AAPL", "NVDA", "TSLA"])
    alerts = load_json(ALERTS_FILE, [])
    date = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    # Combine Watchlist + Institutional so we scan both
    scan_pool = list(set(INSTITUTIONAL_UNIVERSE + watchlist))
    
    print(f"⚡ VULCAN ENGINE: Scanning {len(scan_pool)} stocks...")

    with ProcessPoolExecutor() as executor:
        results = [r for r in list(executor.map(analyze_stock, scan_pool)) if r]

    # 1. PRICE ALERTS CHECK
    active_alerts = []
    for alert in alerts:
        current = next((r for r in results if r['ticker'] == alert['ticker']), None)
        if current:
            # Check if price hit target
            if (alert['type'] == 'above' and current['price'] >= alert['target']) or \
               (alert['type'] == 'below' and current['price'] <= alert['target']):
                msg = f"🔔 ALERT: {alert['ticker']} hit {current['price']} (Target: {alert['target']})"
                print(msg)
                send_email(f"Vulcan Alert: {alert['ticker']}", msg)
            else:
                active_alerts.append(alert) # Keep if not hit yet
    save_json(ALERTS_FILE, active_alerts)

    # 2. TRADE EXECUTION
    ranked_buys = sorted([r for r in results if r['prediction'] == 1], key=lambda x: x['prob'], reverse=True)

    # Manage Sells
    for ticker, pos in list(portfolio["positions"].items()):
        if pos.get("shares", 0) > 0:
            data = next((r for r in results if r['ticker'] == ticker), None)
            if data and data['prediction'] == 0:
                revenue = pos['shares'] * data['price']
                profit = (data['price'] - pos['buy_price']) * pos['shares']
                portfolio["cash"] += revenue
                portfolio["positions"][ticker] = {"shares": 0, "buy_price": 0}
                msg = f"SELL {ticker} | Profit: ${profit:.2f}"
                portfolio["trades"].append(f"{date}: {msg}")
                send_email(f"Vulcan Trade: SELL {ticker}", msg)
                print(f"🛑 {msg}")

    # Manage Buys (Cap at 4 positions)
    slots = sum(1 for p in portfolio["positions"].values() if p.get("shares", 0) > 0)
    for signal in ranked_buys:
        if slots >= 4: break
        ticker = signal['ticker']
        if portfolio["positions"].get(ticker, {}).get("shares", 0) == 0 and signal['prob'] > 0.55:
            shares = int(2500 / signal['price']) # $2500 per slot
            if portfolio["cash"] >= (shares * signal['price']):
                portfolio["cash"] -= (shares * signal['price'])
                portfolio["positions"][ticker] = {"shares": shares, "buy_price": signal['price']}
                slots += 1
                msg = f"BUY {ticker} | {shares} shares @ {signal['price']}"
                portfolio["trades"].append(f"{date}: {msg}")
                send_email(f"Vulcan Trade: BUY {ticker}", msg)
                print(f"✅ {msg}")

    save_json(PORTFOLIO_FILE, portfolio)
    print("Done.")

if __name__ == "__main__":
    run_bot()
   