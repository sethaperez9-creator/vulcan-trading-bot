from flask import Flask, render_template_string, jsonify, request
import yfinance as yf
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
import json
import os
from trader import analyze_stock, run_bot, WATCHLIST

app = Flask(__name__)
PORTFOLIO_FILE = "portfolio.json"

def load_portfolio():
    if os.path.exists(PORTFOLIO_FILE):
        with open(PORTFOLIO_FILE, "r") as f:
            return json.load(f)
    return {"cash": 10000, "positions": {}, "trades": []}

@app.route("/")
def dashboard():
    portfolio = load_portfolio()
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
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Vulcan Trading Bot</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <meta http-equiv="refresh" content="300">
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
            @media (max-width: 600px) {
                .stocks { grid-template-columns: 1fr; }
                .summary { grid-template-columns: 1fr 1fr; }
                h1 { font-size: 20px; }
                .run-btn { font-size: 14px; padding: 12px; }
            }
            .stock-card { background: #12121a; border-radius: 12px; padding: 18px; }
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
            .holding { margin-top: 12px; padding: 10px; background: #0a0a0f; border-radius: 8px; font-size: 13px; color: #00ff88; }
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

        <button class="run-btn" onclick="runBot()" id="runBtn">▶ Run Bot Now</button>

        <div class="search-box" style="margin-bottom: 25px;">
            <input id="tickerInput" type="text" placeholder="Search any stock... (e.g. TSLA, GOOGL)"
                style="width: 100%; padding: 14px; background: #12121a; border: 1px solid #333; border-radius: 12px; color: #fff; font-size: 15px; outline: none;">
            <div id="searchResult" style="margin-top: 12px;"></div>
        </div>

        <button class="run-btn" onclick="getRecommendations()" id="recBtn"
            style="background:#1a1a2e; color:#00ff88; border:1px solid #00ff88; margin-bottom:25px;">
            ⚡ Get Vulcan Recommendations
        </button>
        <div id="recommendations" style="margin-bottom:25px;"></div>

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
            </div>
            {% endfor %}
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

        <script>
            function runBot() {
                const btn = document.getElementById('runBtn');
                btn.disabled = true;
                btn.innerText = '⏳ Running...';
                fetch('/run')
                    .then(res => res.json())
                    .then(data => {
                        btn.innerText = '✅ Done! Refreshing...';
                        setTimeout(() => location.reload(), 1500);
                    })
                    .catch(err => {
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
                                    <div style="background:#12121a; border:1px solid #222; border-radius:12px; padding:18px;">
                                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
                                            <span style="font-size:20px; font-weight:bold;">${data.ticker}</span>
                                            <span style="padding:4px 10px; border-radius:20px; font-size:13px;
                                                ${data.prediction === 1 ? 'background:#00ff8822; color:#00ff88; border:1px solid #00ff8844;' : 'background:#ff445522; color:#ff4455; border:1px solid #ff445544;'}">
                                                ${data.prediction === 1 ? '📈 BUY' : '📉 SELL'}
                                            </span>
                                        </div>
                                        <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px;">
                                            <div style="background:#0a0a0f; border-radius:8px; padding:8px 12px;">
                                                <div style="color:#555; font-size:10px; text-transform:uppercase;">Price</div>
                                                <div style="font-size:15px; font-weight:bold;">$${data.price}</div>
                                            </div>
                                            <div style="background:#0a0a0f; border-radius:8px; padding:8px 12px;">
                                                <div style="color:#555; font-size:10px; text-transform:uppercase;">RSI</div>
                                                <div style="font-size:15px; font-weight:bold; color:${data.rsi > 70 ? '#ff4455' : data.rsi < 30 ? '#00ff88' : '#fff'}">${data.rsi}</div>
                                            </div>
                                            <div style="background:#0a0a0f; border-radius:8px; padding:8px 12px;">
                                                <div style="color:#555; font-size:10px; text-transform:uppercase;">MA50</div>
                                                <div style="font-size:15px; font-weight:bold;">${data.ma50}</div>
                                            </div>
                                            <div style="background:#0a0a0f; border-radius:8px; padding:8px 12px;">
                                                <div style="color:#555; font-size:10px; text-transform:uppercase;">MA200</div>
                                                <div style="font-size:15px; font-weight:bold;">${data.ma200}</div>
                                            </div>
                                            <div style="background:#0a0a0f; border-radius:8px; padding:8px 12px; grid-column: span 2;">
                                                <div style="color:#555; font-size:10px; text-transform:uppercase;">Confidence</div>
                                                <div style="font-size:15px; font-weight:bold; color:${confColor}">${data.confidence}</div>
                                            </div>
                                        </div>
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

                        let html = '<div style="background:#12121a; border:1px solid #222; border-radius:12px; padding:18px;">';
                        html += '<h2 style="color:#888; font-size:14px; text-transform:uppercase; letter-spacing:1px; margin-bottom:15px;">⚡ Vulcan Recommendations</h2>';

                        if (data.buys.length > 0) {
                            html += '<h3 style="color:#00ff88; margin-bottom:10px;">Strong Buys</h3>';
                            data.buys.forEach(stock => {
                                html += `<div style="padding:10px; background:#0a0a0f; border-radius:8px; margin-bottom:8px; display:flex; justify-content:space-between; align-items:center;">
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
                                html += `<div style="padding:10px; background:#0a0a0f; border-radius:8px; margin-bottom:8px; display:flex; justify-content:space-between; align-items:center;">
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
                    .catch(err => {
                        btn.disabled = false;
                        btn.innerText = '⚡ Get Vulcan Recommendations';
                        div.innerHTML = '<p style="color:#ff4455">Error scanning market. Try again.</p>';
                    });
            }
        </script>
    </body>
    </html>
    """
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

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")
    