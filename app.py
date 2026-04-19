from flask import Flask, render_template_string, jsonify, request
import yfinance as yf
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
import json
import os
from trader import analyze_stock, run_bot, load_watchlist, save_watchlist

app = Flask(__name__)
PORTFOLIO_FILE = "portfolio.json"
HOLDINGS_FILE = "holdings.json"
SETTINGS_FILE = "settings.json"

def load_portfolio():
    if os.path.exists(PORTFOLIO_FILE):
        with open(PORTFOLIO_FILE, "r") as f:
            return json.load(f)
    return {"cash": 10000, "positions": {}, "trades": []}

def load_holdings():
    if os.path.exists(HOLDINGS_FILE):
        with open(HOLDINGS_FILE, "r") as f:
            return json.load(f)
    return []

@app.route("/")
def dashboard():
    portfolio = load_portfolio()
    WATCHLIST = load_watchlist()
    stocks = []

    for ticker in WATCHLIST:
        data = analyze_stock(ticker)
        if data:
            position = portfolio["positions"].get(ticker, {"shares": 0, "buy_price": 0})
            data["shares"] = position["shares"]
            data["buy_price"] = position["buy_price"]
            stocks.append(data)

    total = portfolio["cash"]
    for ticker, pos in portfolio["positions"].items():
        for s in stocks:
            if s["ticker"] == ticker and pos["shares"] > 0:
                total += pos["shares"] * s["price"]

    returns = round(((total - 10000) / 10000) * 100, 2)

    # Market summary
    market = []
    for ticker, name in [("SPY", "S&P 500"), ("QQQ", "Nasdaq"), ("DIA", "Dow Jones")]:
        try:
            d = yf.Ticker(ticker).history(period="2d")
            if len(d) >= 2:
                price = round(d["Close"].iloc[-1], 2)
                prev = round(d["Close"].iloc[-2], 2)
                change = round(((price - prev) / prev) * 100, 2)
                market.append({"name": name, "price": price, "change": change})
        except:
            pass

    return render_template_string(html, stocks=stocks, portfolio=portfolio, total=total, returns=returns, market=market)

@app.route("/run")
def run():
    run_bot()
    return jsonify({"status": "done"})

@app.route("/search")
def search():
    ticker = request.args.get("ticker", "").upper()
    if not ticker:
        return jsonify({"error": "No ticker provided"})
    data = analyze_stock(ticker)
    if not data:
        return jsonify({"error": "Stock not found"})
    return jsonify(data)

@app.route("/recommend")
def recommend():
    SCAN_LIST = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA", "META", "SPY", "QQQ", "AMD", "NFLX", "DIS", "BRK-B", "JPM", "BAC"]
    buys = []
    sells = []
    for ticker in SCAN_LIST:
        data = analyze_stock(ticker)
        if data and data["confidence"] == "High":
            if data["prediction"] == 1:
                buys.append(data)
            else:
                sells.append(data)
    buys.sort(key=lambda x: x["rsi"])
    sells.sort(key=lambda x: x["rsi"], reverse=True)
    return jsonify({"buys": buys, "sells": sells})

@app.route("/add_stock", methods=["POST"])
def add_stock():
    ticker = request.json.get("ticker", "").upper()
    if not ticker:
        return jsonify({"error": "No ticker provided"})
    watchlist = load_watchlist()
    if ticker not in watchlist:
        watchlist.append(ticker)
        save_watchlist(watchlist)
    return jsonify({"status": "added", "watchlist": watchlist})

@app.route("/remove_stock", methods=["POST"])
def remove_stock():
    ticker = request.json.get("ticker", "").upper()
    watchlist = load_watchlist()
    if ticker in watchlist:
        watchlist.remove(ticker)
        save_watchlist(watchlist)
    return jsonify({"status": "removed", "watchlist": watchlist})

@app.route("/alerts")
def get_alerts():
    from trader import load_alerts, check_alerts, load_settings, send_alert_email
    triggered = check_alerts()
    settings = load_settings()
    for alert in triggered:
        send_alert_email(alert, settings)
    alerts = load_alerts()
    return jsonify({"alerts": alerts, "triggered": triggered})

@app.route("/add_alert", methods=["POST"])
def add_alert():
    from trader import load_alerts, save_alerts
    data = request.json
    ticker = data.get("ticker", "").upper()
    target = float(data.get("target", 0))
    direction = data.get("direction", "above")
    if not ticker or not target:
        return jsonify({"error": "Missing data"})
    alerts = load_alerts()
    alerts.append({"ticker": ticker, "target": target, "direction": direction})
    save_alerts(alerts)
    return jsonify({"status": "added"})

@app.route("/remove_alert", methods=["POST"])
def remove_alert():
    from trader import load_alerts, save_alerts
    data = request.json
    index = data.get("index", -1)
    alerts = load_alerts()
    if 0 <= index < len(alerts):
        alerts.pop(index)
        save_alerts(alerts)
    return jsonify({"status": "removed"})

@app.route("/save_settings", methods=["POST"])
def save_settings_route():
    data = request.json
    with open(SETTINGS_FILE, "w") as f:
        json.dump(data, f)
    return jsonify({"status": "saved"})

@app.route("/holdings")
def get_holdings():
    holdings = load_holdings()
    enriched = []
    for h in holdings:
        data = analyze_stock(h["ticker"])
        if data:
            current = data["price"]
            cost = h["shares"] * h["buy_price"]
            value = h["shares"] * current
            pnl = round(value - cost, 2)
            pnl_pct = round(((value - cost) / cost) * 100, 2)
            enriched.append({
                **h,
                "current_price": current,
                "value": round(value, 2),
                "pnl": pnl,
                "pnl_pct": pnl_pct,
                "signal": "📈 BUY" if data["prediction"] == 1 else "📉 SELL",
                "confidence": data["confidence"]
            })
    return jsonify(enriched)

@app.route("/add_holding", methods=["POST"])
def add_holding():
    data = request.json
    ticker = data.get("ticker", "").upper()
    shares = float(data.get("shares", 0))
    buy_price = float(data.get("buy_price", 0))
    if not ticker or not shares or not buy_price:
        return jsonify({"error": "Missing data"})
    holdings = load_holdings()
    holdings.append({"ticker": ticker, "shares": shares, "buy_price": buy_price})
    with open(HOLDINGS_FILE, "w") as f:
        json.dump(holdings, f)
    return jsonify({"status": "added"})

@app.route("/remove_holding", methods=["POST"])
def remove_holding():
    data = request.json
    index = data.get("index", -1)
    holdings = load_holdings()
    if 0 <= index < len(holdings):
        holdings.pop(index)
        with open(HOLDINGS_FILE, "w") as f:
            json.dump(holdings, f)
    return jsonify({"status": "removed"})

@app.route("/chart/<ticker>")
def chart(ticker):
    try:
        stock = yf.Ticker(ticker)
        history = stock.history(period="6mo")
        history["MA50"] = history["Close"].rolling(window=50).mean()
        history["MA200"] = history["Close"].rolling(window=200).mean()
        dates = history.index.strftime("%Y-%m-%d").tolist()
        closes = [round(x, 2) for x in history["Close"].tolist()]
        ma50 = [round(x, 2) if not pd.isna(x) else None for x in history["MA50"].tolist()]
        ma200 = [round(x, 2) if not pd.isna(x) else None for x in history["MA200"].tolist()]
        return jsonify({"dates": dates, "closes": closes, "ma50": ma50, "ma200": ma200})
    except:
        return jsonify({"error": "Could not load chart"})

html = """
<!DOCTYPE html>
<html>
<head>
    <title>Vulcan Trading Bot</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta http-equiv="refresh" content="300">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.0/chart.umd.min.js"></script>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: 'Segoe UI', sans-serif; background: #0a0a0f; color: #fff; padding: 20px; }
        h1 { color: #00ff88; font-size: 24px; margin-bottom: 5px; }
        .subtitle { color: #555; font-size: 13px; margin-bottom: 25px; }
        .summary { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin-bottom: 25px; }
        .summary-card { background: #12121a; border: 1px solid #222; border-radius: 12px; padding: 15px; }
        .summary-card .label { color: #555; font-size: 11px; text-transform: uppercase; letter-spacing: 1px; }
        .summary-card .value { font-size: 22px; font-weight: bold; margin-top: 5px; }
        .green { color: #00ff88; }
        .red { color: #ff4455; }
        .stocks { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 15px; margin-bottom: 25px; }
        .stock-card { border-radius: 12px; padding: 18px; background: #12121a; }
        .stock-card-buy { border: 1px solid #00ff8844; }
        .stock-card-sell { border: 1px solid #ff445544; }
        .stock-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
        .ticker { font-size: 20px; font-weight: bold; }
        .signal { font-size: 13px; padding: 4px 10px; border-radius: 20px; }
        .signal-up { background: #00ff8822; color: #00ff88; border: 1px solid #00ff8844; }
        .signal-down { background: #ff445522; color: #ff4455; border: 1px solid #ff445544; }
        .stock-stats { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
        .stat { background: #0a0a0f; border-radius: 8px; padding: 8px 12px; }
        .stat .slabel { color: #555; font-size: 10px; text-transform: uppercase; }
        .stat .svalue { font-size: 15px; font-weight: bold; margin-top: 2px; }
        .holding { margin-top: 8px; padding: 10px; background: #0a0a0f; border-radius: 8px; font-size: 13px; color: #00ff88; }
        .chart-btn { margin-top: 8px; width: 100%; padding: 8px; background: #1a1a2e; color: #00ff88; border: 1px solid #00ff8844; border-radius: 8px; cursor: pointer; font-size: 13px; }
        .trades { background: #12121a; border: 1px solid #222; border-radius: 12px; padding: 18px; margin-bottom: 25px; }
        .trades h2 { color: #888; font-size: 14px; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 15px; }
        .trade-item { padding: 10px 0; border-bottom: 1px solid #1a1a1a; font-size: 13px; color: #aaa; }
        .trade-item:last-child { border-bottom: none; }
        .run-btn { display: block; width: 100%; padding: 16px; background: #00ff88; color: #000; font-size: 16px; font-weight: bold; border: none; border-radius: 12px; cursor: pointer; margin-bottom: 25px; }
        .run-btn:hover { background: #00cc70; }
        .run-btn:disabled { background: #333; color: #666; cursor: not-allowed; }
        .no-trades { color: #444; font-size: 13px; }
        .confidence-high { color: #00ff88; }
        .confidence-medium { color: #ffcc00; }
        .confidence-low { color: #888; }
        .card { background: #12121a; border: 1px solid #222; border-radius: 12px; padding: 18px; margin-bottom: 25px; }
        .card-title { color: #888; font-size: 14px; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 15px; }
        .input-row { display: grid; gap: 10px; margin-bottom: 15px; }
        .input-field { padding: 12px; background: #0a0a0f; border: 1px solid #333; border-radius: 8px; color: #fff; font-size: 14px; outline: none; width: 100%; }
        .add-btn { padding: 12px 20px; background: #00ff88; color: #000; border: none; border-radius: 8px; font-weight: bold; cursor: pointer; width: 100%; }
        .modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.8); z-index: 1000; justify-content: center; align-items: center; }
        .modal.active { display: flex; }
        .modal-content { background: #12121a; border: 1px solid #333; border-radius: 12px; padding: 20px; width: 90%; max-width: 700px; }
        .modal-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; }
        .close-btn { color: #ff4455; cursor: pointer; font-size: 20px; }
        @media (max-width: 600px) {
            .stocks { grid-template-columns: 1fr; }
            .summary { grid-template-columns: 1fr 1fr; }
            h1 { font-size: 20px; }
            .run-btn { font-size: 14px; padding: 12px; }
            input, select { font-size: 16px !important; }
            .input-row { grid-template-columns: 1fr !important; }
        }
    </style>
</head>
<body>
    <h1>⚡ Vulcan Trading Bot</h1>
    <p class="subtitle">Paper trading dashboard — updates on demand</p>

    <div class="summary" style="margin-bottom:15px;">
        {% for index in market %}
        <div class="summary-card">
            <div class="label">{{ index.name }}</div>
            <div class="value {{ 'green' if index.change >= 0 else 'red' }}">${{ index.price }}</div>
            <div style="font-size:13px; color:{{ '#00ff88' if index.change >= 0 else '#ff4455' }}">
                {{ '+' if index.change >= 0 else '' }}{{ index.change }}%
            </div>
        </div>
        {% endfor %}
    </div>

    <div class="summary">
        <div class="summary-card">
            <div class="label">Portfolio Value</div>
            <div class="value {{ 'green' if returns >= 0 else 'red' }}">${{ "%.2f"|format(total) }}</div>
        </div>
        <div class="summary-card">
            <div class="label">Cash</div>
            <div class="value">${{ "%.2f"|format(portfolio.cash) }}</div>
        </div>
        <div class="summary-card">
            <div class="label">Return</div>
            <div class="value {{ 'green' if returns >= 0 else 'red' }}">{{ returns }}%</div>
        </div>
        <div class="summary-card">
            <div class="label">Stocks Watched</div>
            <div class="value">{{ stocks|length }}</div>
        </div>
    </div>

    <br>
    <button class="run-btn" onclick="runBot()" id="runBtn">▶ Run Bot Now</button>

    <div class="card">
        <div class="card-title">🔍 Search Any Stock</div>
        <input id="tickerInput" type="text" class="input-field" placeholder="Search any stock... (e.g. TSLA, GOOGL)">
        <div id="searchResult" style="margin-top: 12px;"></div>
    </div>

    <button class="run-btn" onclick="getRecommendations()" id="recBtn"
        style="background:#1a1a2e; color:#00ff88; border:1px solid #00ff88; margin-bottom:25px;">
        ⚡ Get Vulcan Recommendations
    </button>
    <div id="recommendations" style="margin-bottom:25px;"></div>

    <div class="card">
        <div class="card-title">📋 Watchlist Manager</div>
        <div class="input-row" style="grid-template-columns: 1fr auto;">
            <input id="addTickerInput" type="text" class="input-field" placeholder="Add stock... (e.g. TSLA)">
            <button onclick="addStock()" class="add-btn" style="width:auto; padding:12px 20px;">+ Add</button>
        </div>
        <div style="display:flex; flex-wrap:wrap; gap:8px;">
            {% for stock in stocks %}
            <div style="background:#0a0a0f; border:1px solid #333; border-radius:20px; padding:6px 12px; display:flex; align-items:center; gap:8px;">
                <span style="font-weight:bold;">{{ stock.ticker }}</span>
                <span onclick="removeStock('{{ stock.ticker }}')" style="color:#ff4455; cursor:pointer; font-size:16px;">×</span>
            </div>
            {% endfor %}
        </div>
    </div>

    <div class="stocks">
        {% for stock in stocks %}
        <div class="stock-card {{ 'stock-card-buy' if stock.prediction == 1 else 'stock-card-sell' }}">
            <div class="stock-header">
                <div class="ticker">{{ stock.ticker }}</div>
                <div class="signal {{ 'signal-up' if stock.prediction == 1 else 'signal-down' }}">
                    {{ '📈 BUY' if stock.prediction == 1 else '📉 SELL' }}
                </div>
            </div>
            <div class="stock-stats">
                <div class="stat">
                    <div class="slabel">Price</div>
                    <div class="svalue">${{ stock.price }}</div>
                </div>
                <div class="stat">
                    <div class="slabel">RSI</div>
                    <div class="svalue {{ 'red' if stock.rsi > 70 else 'green' if stock.rsi < 30 else '' }}">{{ stock.rsi }}</div>
                </div>
                <div class="stat">
                    <div class="slabel">MA50</div>
                    <div class="svalue">{{ stock.ma50 }}</div>
                </div>
                <div class="stat">
                    <div class="slabel">MA200</div>
                    <div class="svalue">{{ stock.ma200 }}</div>
                </div>
            </div>
            <div class="stat" style="margin-top:8px;">
                <div class="slabel">Confidence</div>
                <div class="svalue confidence-{{ stock.confidence | lower }}">{{ stock.confidence }}</div>
            </div>
            {% if stock.shares > 0 %}
            <div class="holding">✅ Holding {{ stock.shares }} shares @ ${{ stock.buy_price }}</div>
            {% endif %}
            <button class="chart-btn" onclick="showChart('{{ stock.ticker }}')">📈 View Chart</button>
        </div>
        {% endfor %}
    </div>

    <div class="card">
        <div class="card-title">🔔 Price Alerts</div>
        <div class="input-row" style="grid-template-columns: 1fr 1fr 1fr auto;">
            <input id="alertTicker" type="text" class="input-field" placeholder="Ticker (e.g. AAPL)">
            <input id="alertTarget" type="number" class="input-field" placeholder="Target price">
            <select id="alertDirection" class="input-field">
                <option value="above">Rises above</option>
                <option value="below">Falls below</option>
            </select>
            <button onclick="addAlert()" class="add-btn" style="width:auto; padding:12px 20px;">+ Add</button>
        </div>
        <div id="alertsList" style="margin-bottom:15px;">
            <p style="color:#444; font-size:13px;">Loading alerts...</p>
        </div>
        <div style="border-top:1px solid #222; padding-top:15px; margin-top:15px;">
            <div class="card-title">📧 Email Settings</div>
            <p style="color:#555; font-size:12px; margin-bottom:10px; line-height:1.6;">
                To receive email alerts, enter your email address, a Gmail account to send from, and a Gmail App Password
                (not your regular password). To get an App Password: go to
                <span style="color:#00ff88;">myaccount.google.com → Security → App Passwords</span>,
                make sure 2-Step Verification is enabled, create a new app password named "Vulcan",
                and paste the 16-character code below.
            </p>
            <div class="input-row" style="grid-template-columns: 1fr 1fr 1fr auto;">
                <input id="settingsEmail" type="email" class="input-field" placeholder="Your email">
                <input id="settingsGmailUser" type="email" class="input-field" placeholder="Gmail sender">
                <input id="settingsGmailPass" type="password" class="input-field" placeholder="Gmail app password">
                <button onclick="saveSettings()" style="padding:12px 20px; background:#1a1a2e; color:#00ff88; border:1px solid #00ff88; border-radius:8px; font-weight:bold; cursor:pointer; width:auto;">Save</button>
            </div>
        </div>
    </div>

    <div class="card">
        <div class="card-title">💼 My Real Portfolio</div>
        <p style="color:#555; font-size:12px; margin-bottom:15px;">Enter your real holdings from Webull or any broker to track P&L and get Vulcan's signal on each position.</p>
        <div class="input-row" style="grid-template-columns: 1fr 1fr 1fr auto;">
            <input id="holdingTicker" type="text" class="input-field" placeholder="Ticker (e.g. AAPL)">
            <input id="holdingShares" type="number" class="input-field" placeholder="Shares owned">
            <input id="holdingBuyPrice" type="number" class="input-field" placeholder="Avg buy price">
            <button onclick="addHolding()" class="add-btn" style="width:auto; padding:12px 20px;">+ Add</button>
        </div>
        <div id="holdingsList">
            <p style="color:#444; font-size:13px;">Loading portfolio...</p>
        </div>
    </div>

    <div class="trades">
        <h2>Trade History</h2>
        {% if portfolio.trades %}
            {% for trade in portfolio.trades|reverse %}
            <div class="trade-item">{{ trade }}</div>
            {% endfor %}
        {% else %}
            <div class="no-trades">No trades yet — run the bot to start trading.</div>
        {% endif %}
    </div>

    <!-- Chart Modal -->
    <div class="modal" id="chartModal">
        <div class="modal-content">
            <div class="modal-header">
                <h2 id="chartTitle" style="color:#00ff88;">Chart</h2>
                <span class="close-btn" onclick="closeChart()">× Close</span>
            </div>
            <canvas id="stockChart"></canvas>
        </div>
    </div>

    <script>
        let chartInstance = null;

        function runBot() {
            const btn = document.getElementById('runBtn');
            btn.disabled = true;
            btn.innerText = '⏳ Running...';
            fetch('/run')
                .then(res => res.json())
                .then(() => {
                    btn.innerText = '✅ Done! Refreshing...';
                    setTimeout(() => location.reload(), 1500);
                })
                .catch(() => {
                    btn.innerText = '❌ Error — try again';
                    btn.disabled = false;
                });
        }

        document.getElementById('tickerInput').addEventListener('keydown', function(e) {
            if (e.key === 'Enter') {
                const ticker = this.value.trim().toUpperCase();
                if (!ticker) return;
                const result = document.getElementById('searchResult');
                result.innerHTML = '<p style="color:#555">Analyzing ' + ticker + '...</p>';
                fetch('/search?ticker=' + ticker)
                    .then(res => res.json())
                    .then(data => {
                        if (data.error) {
                            result.innerHTML = '<p style="color:#ff4455">Could not find ' + ticker + '</p>';
                        } else {
                            const confColor = data.confidence === 'High' ? '#00ff88' : data.confidence === 'Medium' ? '#ffcc00' : '#888';
                            result.innerHTML = `
                                <div style="background:#0a0a0f; border:1px solid #222; border-radius:12px; padding:18px;">
                                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px; flex-wrap:wrap; gap:8px;">
                                        <span style="font-size:20px; font-weight:bold;">${data.ticker}</span>
                                        <span style="padding:4px 10px; border-radius:20px; font-size:13px;
                                            ${data.prediction === 1 ? 'background:#00ff8822; color:#00ff88; border:1px solid #00ff8844;' : 'background:#ff445522; color:#ff4455; border:1px solid #ff445544;'}">
                                            ${data.prediction === 1 ? '📈 BUY' : '📉 SELL'}
                                        </span>
                                    </div>
                                    <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px;">
                                        <div style="background:#12121a; border-radius:8px; padding:8px 12px;">
                                            <div style="color:#555; font-size:10px; text-transform:uppercase;">Price</div>
                                            <div style="font-size:15px; font-weight:bold;">$${data.price}</div>
                                        </div>
                                        <div style="background:#12121a; border-radius:8px; padding:8px 12px;">
                                            <div style="color:#555; font-size:10px; text-transform:uppercase;">RSI</div>
                                            <div style="font-size:15px; font-weight:bold; color:${data.rsi > 70 ? '#ff4455' : data.rsi < 30 ? '#00ff88' : '#fff'}">${data.rsi}</div>
                                        </div>
                                        <div style="background:#12121a; border-radius:8px; padding:8px 12px;">
                                            <div style="color:#555; font-size:10px; text-transform:uppercase;">MA50</div>
                                            <div style="font-size:15px; font-weight:bold;">${data.ma50}</div>
                                        </div>
                                        <div style="background:#12121a; border-radius:8px; padding:8px 12px;">
                                            <div style="color:#555; font-size:10px; text-transform:uppercase;">MA200</div>
                                            <div style="font-size:15px; font-weight:bold;">${data.ma200}</div>
                                        </div>
                                        <div style="background:#12121a; border-radius:8px; padding:8px 12px; grid-column:span 2;">
                                            <div style="color:#555; font-size:10px; text-transform:uppercase;">Confidence</div>
                                            <div style="font-size:15px; font-weight:bold; color:${confColor}">${data.confidence}</div>
                                        </div>
                                    </div>
                                    <button onclick="showChart('${data.ticker}')" class="chart-btn" style="margin-top:10px;">📈 View Chart</button>
                                </div>`;
                        }
                    });
            }
        });

        function getRecommendations() {
            const btn = document.getElementById('recBtn');
            const div = document.getElementById('recommendations');
            btn.disabled = true;
            btn.innerText = '⏳ Scanning market...';
            div.innerHTML = '';
            fetch('/recommend')
                .then(res => res.json())
                .then(data => {
                    btn.disabled = false;
                    btn.innerText = '⚡ Get Vulcan Recommendations';
                    let html = '<div class="card">';
                    html += '<div class="card-title">⚡ Vulcan Recommendations</div>';
                    if (data.buys.length > 0) {
                        html += '<h3 style="color:#00ff88; margin-bottom:10px;">Strong Buys</h3>';
                        data.buys.forEach(stock => {
                            html += `<div style="padding:10px; background:#0a0a0f; border-radius:8px; margin-bottom:8px; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
                                <span style="font-weight:bold;">${stock.ticker}</span>
                                <span style="color:#555; font-size:13px;">RSI: ${stock.rsi}</span>
                                <span style="color:#555; font-size:13px;">$${stock.price}</span>
                                <span style="color:#00ff88; font-size:13px;">📈 ${stock.confidence} Confidence</span>
                            </div>`;
                        });
                    } else {
                        html += '<p style="color:#444; margin-bottom:15px;">No strong buy signals right now.</p>';
                    }
                    if (data.sells.length > 0) {
                        html += '<h3 style="color:#ff4455; margin-top:15px; margin-bottom:10px;">Strong Sells</h3>';
                        data.sells.forEach(stock => {
                            html += `<div style="padding:10px; background:#0a0a0f; border-radius:8px; margin-bottom:8px; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
                                <span style="font-weight:bold;">${stock.ticker}</span>
                                <span style="color:#555; font-size:13px;">RSI: ${stock.rsi}</span>
                                <span style="color:#555; font-size:13px;">$${stock.price}</span>
                                <span style="color:#ff4455; font-size:13px;">📉 ${stock.confidence} Confidence</span>
                            </div>`;
                        });
                    } else {
                        html += '<p style="color:#444; margin-top:15px;">No strong sell signals right now.</p>';
                    }
                    html += '</div>';
                    div.innerHTML = html;
                })
                .catch(() => {
                    btn.disabled = false;
                    btn.innerText = '⚡ Get Vulcan Recommendations';
                    div.innerHTML = '<p style="color:#ff4455">Error scanning market. Try again.</p>';
                });
        }

        function addStock() {
            const input = document.getElementById('addTickerInput');
            const ticker = input.value.trim().toUpperCase();
            if (!ticker) return;
            fetch('/add_stock', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ticker})
            }).then(() => location.reload());
        }

        function removeStock(ticker) {
            fetch('/remove_stock', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ticker})
            }).then(() => location.reload());
        }

        function loadAlerts() {
            fetch('/alerts')
                .then(res => res.json())
                .then(data => {
                    const div = document.getElementById('alertsList');
                    if (data.triggered.length > 0) {
                        data.triggered.forEach(alert => {
                            const banner = document.createElement('div');
                            banner.style = 'background:#00ff8822; border:1px solid #00ff88; border-radius:8px; padding:10px; margin-bottom:8px; color:#00ff88; font-size:13px;';
                            banner.innerHTML = `🔔 ${alert.ticker} hit $${alert.current_price} (target: $${alert.target} ${alert.direction})`;
                            document.body.insertBefore(banner, document.body.firstChild);
                        });
                    }
                    if (data.alerts.length === 0) {
                        div.innerHTML = '<p style="color:#444; font-size:13px;">No active alerts.</p>';
                    } else {
                        div.innerHTML = data.alerts.map((alert, i) => `
                            <div style="padding:10px; background:#0a0a0f; border-radius:8px; margin-bottom:8px; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
                                <span style="font-weight:bold;">${alert.ticker}</span>
                                <span style="color:#555; font-size:13px;">${alert.direction} $${alert.target}</span>
                                <span onclick="removeAlert(${i})" style="color:#ff4455; cursor:pointer;">× Remove</span>
                            </div>
                        `).join('');
                    }
                });
        }

        function addAlert() {
            const ticker = document.getElementById('alertTicker').value.trim().toUpperCase();
            const target = document.getElementById('alertTarget').value;
            const direction = document.getElementById('alertDirection').value;
            if (!ticker || !target) return;
            fetch('/add_alert', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ticker, target: parseFloat(target), direction})
            }).then(() => loadAlerts());
        }

        function removeAlert(index) {
            fetch('/remove_alert', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({index})
            }).then(() => loadAlerts());
        }

        function saveSettings() {
            const email = document.getElementById('settingsEmail').value;
            const gmail_user = document.getElementById('settingsGmailUser').value;
            const gmail_pass = document.getElementById('settingsGmailPass').value;
            fetch('/save_settings', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({email, gmail_user, gmail_pass})
            }).then(() => alert('Settings saved!'));
        }

        function loadHoldings() {
            fetch('/holdings')
                .then(res => res.json())
                .then(data => {
                    const div = document.getElementById('holdingsList');
                    if (data.length === 0) {
                        div.innerHTML = '<p style="color:#444; font-size:13px;">No holdings added yet.</p>';
                        return;
                    }
                    let totalValue = 0;
                    let totalPnl = 0;
                    let html = '';
                    data.forEach((h, i) => {
                        totalValue += h.value;
                        totalPnl += h.pnl;
                        html += `
                            <div style="padding:12px; background:#0a0a0f; border-radius:8px; margin-bottom:8px;">
                                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px; flex-wrap:wrap; gap:8px;">
                                    <span style="font-weight:bold; font-size:16px;">${h.ticker}</span>
                                    <span style="font-size:13px; color:${h.pnl >= 0 ? '#00ff88' : '#ff4455'};">
                                        ${h.pnl >= 0 ? '+' : ''}$${h.pnl} (${h.pnl_pct}%)
                                    </span>
                                    <span onclick="removeHolding(${i})" style="color:#ff4455; cursor:pointer;">× Remove</span>
                                </div>
                                <div style="display:grid; grid-template-columns:repeat(2,1fr); gap:8px; font-size:12px; color:#555;">
                                    <div>Shares: <span style="color:#fff;">${h.shares}</span></div>
                                    <div>Avg Cost: <span style="color:#fff;">$${h.buy_price}</span></div>
                                    <div>Current: <span style="color:#fff;">$${h.current_price}</span></div>
                                    <div>Value: <span style="color:#fff;">$${h.value}</span></div>
                                </div>
                                <div style="margin-top:6px; font-size:12px;">
                                    Vulcan: <span style="color:${h.signal.includes('BUY') ? '#00ff88' : '#ff4455'}">${h.signal}</span>
                                    <span style="color:#555; margin-left:8px;">${h.confidence} Confidence</span>
                                </div>
                            </div>`;
                    });
                    html += `
                        <div style="padding:12px; border-top:1px solid #222; margin-top:8px; display:flex; justify-content:space-between; flex-wrap:wrap; gap:8px;">
                            <span style="color:#888;">Total Value</span>
                            <span style="font-weight:bold;">$${totalValue.toFixed(2)}</span>
                            <span style="color:${totalPnl >= 0 ? '#00ff88' : '#ff4455'};">
                                ${totalPnl >= 0 ? '+' : ''}$${totalPnl.toFixed(2)} P&L
                            </span>
                        </div>`;
                    div.innerHTML = html;
                });
        }

        function addHolding() {
            const ticker = document.getElementById('holdingTicker').value.trim().toUpperCase();
            const shares = document.getElementById('holdingShares').value;
            const buy_price = document.getElementById('holdingBuyPrice').value;
            if (!ticker || !shares || !buy_price) return;
            fetch('/add_holding', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ticker, shares: parseFloat(shares), buy_price: parseFloat(buy_price)})
            }).then(() => loadHoldings());
        }

        function removeHolding(index) {
            fetch('/remove_holding', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({index})
            }).then(() => loadHoldings());
        }

        function showChart(ticker) {
            document.getElementById('chartTitle').innerText = ticker + ' — 6 Month Chart';
            document.getElementById('chartModal').classList.add('active');
            fetch('/chart/' + ticker)
                .then(res => res.json())
                .then(data => {
                    if (chartInstance) chartInstance.destroy();
                    const ctx = document.getElementById('stockChart').getContext('2d');
                    chartInstance = new Chart(ctx, {
                        type: 'line',
                        data: {
                            labels: data.dates,
                            datasets: [
                                {
                                    label: 'Price',
                                    data: data.closes,
                                    borderColor: '#00ff88',
                                    borderWidth: 2,
                                    pointRadius: 0,
                                    tension: 0.1
                                },
                                {
                                    label: 'MA50',
                                    data: data.ma50,
                                    borderColor: '#ffcc00',
                                    borderWidth: 1.5,
                                    pointRadius: 0,
                                    tension: 0.1
                                },
                                {
                                    label: 'MA200',
                                    data: data.ma200,
                                    borderColor: '#ff4455',
                                    borderWidth: 1.5,
                                    pointRadius: 0,
                                    tension: 0.1
                                }
                            ]
                        },
                        options: {
                            responsive: true,
                            plugins: {
                                legend: { labels: { color: '#fff' } }
                            },
                            scales: {
                                x: {
                                    ticks: { color: '#555', maxTicksLimit: 6 },
                                    grid: { color: '#1a1a1a' }
                                },
                                y: {
                                    ticks: { color: '#555' },
                                    grid: { color: '#1a1a1a' }
                                }
                            }
                        }
                    });
                });
        }

        function closeChart() {
            document.getElementById('chartModal').classList.remove('active');
            if (chartInstance) chartInstance.destroy();
        }

        loadAlerts();
        loadHoldings();
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")