from flask import Flask, render_template_string, jsonify, request, session, redirect, url_for
import yfinance as yf
import pandas as pd
import json
import os
import hashlib
import secrets
from datetime import datetime
from trader import analyze_stock, run_bot, load_watchlist, save_watchlist, load_alerts, save_alerts, check_alerts, send_alert_email, load_settings, get_chart_data

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)  # Random secret key for sessions

PORTFOLIO_FILE = "portfolio.json"
HOLDINGS_FILE = "holdings.json"
USERS_FILE = "users.json"

# ─── Auth Helpers ─────────────────────────────────────────────────────────────

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r") as f:
            return json.load(f)
    return {}

def save_users(users):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f)

def is_logged_in():
    return "username" in session

def require_login():
    if not is_logged_in():
        return redirect(url_for("login"))
    return None

# ─── Portfolio / Holdings ─────────────────────────────────────────────────────

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

# ─── Login Page ───────────────────────────────────────────────────────────────

LOGIN_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Vulcan — Sign In</title>
    <link href="https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Mono:ital,wght@0,400;0,500;1,400&display=swap" rel="stylesheet">
    <style>
        *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

        :root {
            --bg: #06060a;
            --surface: #0e0e16;
            --border: #1e1e2e;
            --accent: #00ff88;
            --accent-dim: #00ff8820;
            --accent-mid: #00ff8844;
            --red: #ff4455;
            --text: #e8e8f0;
            --muted: #55556a;
            --input-bg: #0a0a12;
        }

        body {
            font-family: 'DM Mono', monospace;
            background: var(--bg);
            color: var(--text);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            position: relative;
            overflow: hidden;
        }

        /* Animated grid background */
        body::before {
            content: '';
            position: fixed;
            inset: 0;
            background-image:
                linear-gradient(rgba(0,255,136,0.03) 1px, transparent 1px),
                linear-gradient(90deg, rgba(0,255,136,0.03) 1px, transparent 1px);
            background-size: 40px 40px;
            animation: gridShift 20s linear infinite;
            pointer-events: none;
        }

        @keyframes gridShift {
            0% { transform: translate(0, 0); }
            100% { transform: translate(40px, 40px); }
        }

        /* Glowing orb */
        body::after {
            content: '';
            position: fixed;
            width: 600px;
            height: 600px;
            border-radius: 50%;
            background: radial-gradient(circle, rgba(0,255,136,0.06) 0%, transparent 70%);
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            pointer-events: none;
            animation: pulse 4s ease-in-out infinite;
        }

        @keyframes pulse {
            0%, 100% { opacity: 0.6; transform: translate(-50%, -50%) scale(1); }
            50% { opacity: 1; transform: translate(-50%, -50%) scale(1.05); }
        }

        .container {
            width: 100%;
            max-width: 420px;
            padding: 20px;
            position: relative;
            z-index: 10;
            animation: fadeUp 0.6s cubic-bezier(0.16, 1, 0.3, 1) both;
        }

        @keyframes fadeUp {
            from { opacity: 0; transform: translateY(24px); }
            to { opacity: 1; transform: translateY(0); }
        }

        .logo {
            text-align: center;
            margin-bottom: 40px;
        }

        .logo-icon {
            font-size: 36px;
            display: block;
            margin-bottom: 10px;
            filter: drop-shadow(0 0 20px rgba(0,255,136,0.5));
            animation: iconGlow 2s ease-in-out infinite;
        }

        @keyframes iconGlow {
            0%, 100% { filter: drop-shadow(0 0 12px rgba(0,255,136,0.4)); }
            50% { filter: drop-shadow(0 0 28px rgba(0,255,136,0.8)); }
        }

        .logo h1 {
            font-family: 'Syne', sans-serif;
            font-size: 32px;
            font-weight: 800;
            color: var(--accent);
            letter-spacing: -1px;
        }

        .logo p {
            font-size: 11px;
            color: var(--muted);
            letter-spacing: 3px;
            text-transform: uppercase;
            margin-top: 4px;
        }

        .card {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 32px;
            position: relative;
            overflow: hidden;
        }

        .card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 1px;
            background: linear-gradient(90deg, transparent, var(--accent-mid), transparent);
        }

        .tabs {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 4px;
            background: var(--input-bg);
            border-radius: 10px;
            padding: 4px;
            margin-bottom: 28px;
        }

        .tab {
            padding: 9px;
            text-align: center;
            border-radius: 7px;
            cursor: pointer;
            font-size: 12px;
            font-weight: 500;
            letter-spacing: 1px;
            text-transform: uppercase;
            color: var(--muted);
            transition: all 0.2s;
            border: none;
            background: none;
            font-family: 'DM Mono', monospace;
        }

        .tab.active {
            background: var(--accent-dim);
            color: var(--accent);
            border: 1px solid var(--accent-mid);
        }

        .form-group {
            margin-bottom: 18px;
        }

        label {
            display: block;
            font-size: 10px;
            text-transform: uppercase;
            letter-spacing: 2px;
            color: var(--muted);
            margin-bottom: 8px;
        }

        input {
            width: 100%;
            padding: 13px 16px;
            background: var(--input-bg);
            border: 1px solid var(--border);
            border-radius: 10px;
            color: var(--text);
            font-size: 14px;
            font-family: 'DM Mono', monospace;
            outline: none;
            transition: border-color 0.2s, box-shadow 0.2s;
        }

        input:focus {
            border-color: var(--accent-mid);
            box-shadow: 0 0 0 3px var(--accent-dim);
        }

        input::placeholder { color: var(--muted); }

        .btn {
            width: 100%;
            padding: 14px;
            background: var(--accent);
            color: #000;
            border: none;
            border-radius: 10px;
            font-size: 13px;
            font-weight: 700;
            font-family: 'Syne', sans-serif;
            letter-spacing: 1px;
            text-transform: uppercase;
            cursor: pointer;
            margin-top: 8px;
            transition: all 0.2s;
            position: relative;
            overflow: hidden;
        }

        .btn::after {
            content: '';
            position: absolute;
            inset: 0;
            background: linear-gradient(135deg, rgba(255,255,255,0.15) 0%, transparent 50%);
        }

        .btn:hover { background: #00e67a; transform: translateY(-1px); box-shadow: 0 8px 24px rgba(0,255,136,0.3); }
        .btn:active { transform: translateY(0); }
        .btn:disabled { background: #333; color: #666; cursor: not-allowed; transform: none; box-shadow: none; }

        .error {
            background: rgba(255,68,85,0.1);
            border: 1px solid rgba(255,68,85,0.3);
            border-radius: 10px;
            padding: 12px 16px;
            font-size: 13px;
            color: var(--red);
            margin-bottom: 18px;
            display: none;
        }

        .error.show { display: block; animation: shake 0.3s ease; }

        @keyframes shake {
            0%, 100% { transform: translateX(0); }
            25% { transform: translateX(-6px); }
            75% { transform: translateX(6px); }
        }

        .success {
            background: rgba(0,255,136,0.1);
            border: 1px solid var(--accent-mid);
            border-radius: 10px;
            padding: 12px 16px;
            font-size: 13px;
            color: var(--accent);
            margin-bottom: 18px;
            display: none;
        }

        .success.show { display: block; }

        .divider {
            height: 1px;
            background: var(--border);
            margin: 24px 0;
        }

        .hint {
            font-size: 11px;
            color: var(--muted);
            text-align: center;
            line-height: 1.6;
        }

        #registerForm { display: none; }

        .loading-dots::after {
            content: '';
            animation: dots 1.2s steps(4, end) infinite;
        }
        @keyframes dots {
            0%   { content: ''; }
            25%  { content: '.'; }
            50%  { content: '..'; }
            75%  { content: '...'; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="logo">
            <span class="logo-icon">⚡</span>
            <h1>VULCAN</h1>
            <p>Trading Intelligence</p>
        </div>

        <div class="card">
            <div class="tabs">
                <button class="tab active" onclick="switchTab('login')">Sign In</button>
                <button class="tab" onclick="switchTab('register')">Register</button>
            </div>

            <div id="errorMsg" class="error"></div>
            <div id="successMsg" class="success"></div>

            <!-- Login Form -->
            <form id="loginForm" onsubmit="handleLogin(event)">
                <div class="form-group">
                    <label>Username</label>
                    <input type="text" id="loginUser" placeholder="your_username" autocomplete="username" required>
                </div>
                <div class="form-group">
                    <label>Password</label>
                    <input type="password" id="loginPass" placeholder="••••••••" autocomplete="current-password" required>
                </div>
                <button type="submit" class="btn" id="loginBtn">Access Dashboard</button>
            </form>

            <!-- Register Form -->
            <form id="registerForm" onsubmit="handleRegister(event)">
                <div class="form-group">
                    <label>Username</label>
                    <input type="text" id="regUser" placeholder="choose_a_username" autocomplete="username" required>
                </div>
                <div class="form-group">
                    <label>Password</label>
                    <input type="password" id="regPass" placeholder="min. 6 characters" autocomplete="new-password" required>
                </div>
                <div class="form-group">
                    <label>Confirm Password</label>
                    <input type="password" id="regConfirm" placeholder="repeat password" autocomplete="new-password" required>
                </div>
                <button type="submit" class="btn" id="registerBtn">Create Account</button>
            </form>

            {% if flash_msg %}
            <script>
                document.addEventListener('DOMContentLoaded', function() {
                    showError("{{ flash_msg }}");
                });
            </script>
            {% endif %}

            <div class="divider"></div>
            <p class="hint">Vulcan paper trades your watchlist using<br>ML signals + RSI + moving averages.</p>
        </div>
    </div>

    <script>
        let currentTab = 'login';

        function switchTab(tab) {
            currentTab = tab;
            document.querySelectorAll('.tab').forEach((t, i) => {
                t.classList.toggle('active', (i === 0 && tab === 'login') || (i === 1 && tab === 'register'));
            });
            document.getElementById('loginForm').style.display = tab === 'login' ? 'block' : 'none';
            document.getElementById('registerForm').style.display = tab === 'register' ? 'block' : 'none';
            clearMessages();
        }

        function showError(msg) {
            const el = document.getElementById('errorMsg');
            el.textContent = '⚠ ' + msg;
            el.className = 'error show';
            document.getElementById('successMsg').className = 'success';
        }

        function showSuccess(msg) {
            const el = document.getElementById('successMsg');
            el.textContent = '✓ ' + msg;
            el.className = 'success show';
            document.getElementById('errorMsg').className = 'error';
        }

        function clearMessages() {
            document.getElementById('errorMsg').className = 'error';
            document.getElementById('successMsg').className = 'success';
        }

        async function handleLogin(e) {
            e.preventDefault();
            const btn = document.getElementById('loginBtn');
            btn.disabled = true;
            btn.innerHTML = 'Authenticating<span class="loading-dots"></span>';
            clearMessages();

            const res = await fetch('/auth/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    username: document.getElementById('loginUser').value.trim(),
                    password: document.getElementById('loginPass').value
                })
            });
            const data = await res.json();

            if (data.success) {
                btn.innerHTML = '✓ Success! Redirecting...';
                window.location.href = '/';
            } else {
                showError(data.error);
                btn.disabled = false;
                btn.innerHTML = 'Access Dashboard';
            }
        }

        async function handleRegister(e) {
            e.preventDefault();
            const pass = document.getElementById('regPass').value;
            const confirm = document.getElementById('regConfirm').value;
            clearMessages();

            if (pass !== confirm) { showError("Passwords don't match."); return; }
            if (pass.length < 6) { showError("Password must be at least 6 characters."); return; }

            const btn = document.getElementById('registerBtn');
            btn.disabled = true;
            btn.innerHTML = 'Creating account<span class="loading-dots"></span>';

            const res = await fetch('/auth/register', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    username: document.getElementById('regUser').value.trim(),
                    password: pass
                })
            });
            const data = await res.json();

            if (data.success) {
                showSuccess('Account created! You can now sign in.');
                setTimeout(() => switchTab('login'), 1500);
            } else {
                showError(data.error);
            }
            btn.disabled = false;
            btn.innerHTML = 'Create Account';
        }
    </script>
</body>
</html>
"""

# ─── Auth Routes ──────────────────────────────────────────────────────────────

@app.route("/login")
def login():
    if is_logged_in():
        return redirect(url_for("dashboard"))
    return render_template_string(LOGIN_HTML, flash_msg="")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/auth/login", methods=["POST"])
def auth_login():
    data = request.json
    username = data.get("username", "").strip().lower()
    password = data.get("password", "")

    if not username or not password:
        return jsonify({"success": False, "error": "Username and password required."})

    users = load_users()
    if username not in users:
        return jsonify({"success": False, "error": "Invalid username or password."})

    if users[username]["password"] != hash_password(password):
        return jsonify({"success": False, "error": "Invalid username or password."})

    session["username"] = username
    session.permanent = True
    return jsonify({"success": True})

@app.route("/auth/register", methods=["POST"])
def auth_register():
    data = request.json
    username = data.get("username", "").strip().lower()
    password = data.get("password", "")

    if not username or not password:
        return jsonify({"success": False, "error": "All fields required."})

    if len(username) < 3:
        return jsonify({"success": False, "error": "Username must be at least 3 characters."})

    if not username.replace("_", "").replace("-", "").isalnum():
        return jsonify({"success": False, "error": "Username can only contain letters, numbers, - and _."})

    users = load_users()
    if username in users:
        return jsonify({"success": False, "error": "Username already taken."})

    users[username] = {
        "password": hash_password(password),
        "created": datetime.now().isoformat()
    }
    save_users(users)
    return jsonify({"success": True})

# ─── Protected Dashboard ──────────────────────────────────────────────────────

@app.route("/")
def dashboard():
    redir = require_login()
    if redir:
        return redir

    username = session["username"]
    WATCHLIST = load_watchlist()
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
        <link href="https://fonts.googleapis.com/css2?family=Syne:wght@400;700;800&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">
        <style>
            * { box-sizing: border-box; margin: 0; padding: 0; }
            body { font-family: 'DM Mono', monospace; background: #06060a; color: #fff; padding: 20px; }
            h1 { color: #00ff88; font-size: 24px; margin-bottom: 5px; font-family: 'Syne', sans-serif; font-weight: 800; }
            .subtitle { color: #555; font-size: 13px; margin-bottom: 25px; }
            .topbar { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 25px; flex-wrap: wrap; gap: 10px; }
            .user-badge { display: flex; align-items: center; gap: 10px; }
            .user-pill { background: #0e0e16; border: 1px solid #1e1e2e; border-radius: 20px; padding: 6px 14px; font-size: 12px; color: #888; display: flex; align-items: center; gap: 6px; }
            .user-pill span { color: #00ff88; }
            .logout-btn { background: none; border: 1px solid #2a2a3a; border-radius: 20px; padding: 6px 14px; color: #555; font-size: 12px; cursor: pointer; font-family: 'DM Mono', monospace; transition: all 0.2s; }
            .logout-btn:hover { border-color: #ff4455; color: #ff4455; }
            .summary { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin-bottom: 25px; }
            .summary-card { background: #0e0e16; border: 1px solid #1e1e2e; border-radius: 12px; padding: 15px; }
            .summary-card .label { color: #555; font-size: 11px; text-transform: uppercase; letter-spacing: 1px; }
            .summary-card .value { font-size: 22px; font-weight: bold; margin-top: 5px; font-family: 'Syne', sans-serif; }
            .green { color: #00ff88; }
            .red { color: #ff4455; }
            .stocks { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 15px; margin-bottom: 25px; }
            .stock-card { border-radius: 12px; padding: 18px; background: #0e0e16; }
            .stock-card-buy { border: 1px solid #00ff8844; }
            .stock-card-sell { border: 1px solid #ff445544; }
            .stock-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
            .ticker { font-size: 20px; font-weight: bold; cursor: pointer; font-family: 'Syne', sans-serif; }
            .ticker:hover { color: #00ff88; }
            .signal { font-size: 13px; padding: 4px 10px; border-radius: 20px; }
            .signal-up { background: #00ff8822; color: #00ff88; border: 1px solid #00ff8844; }
            .signal-down { background: #ff445522; color: #ff4455; border: 1px solid #ff445544; }
            .stock-stats { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
            .stat { background: #06060a; border-radius: 8px; padding: 8px 12px; }
            .stat .slabel { color: #555; font-size: 10px; text-transform: uppercase; }
            .stat .svalue { font-size: 15px; font-weight: bold; margin-top: 2px; }
            .holding { margin-top: 12px; padding: 10px; background: #06060a; border-radius: 8px; font-size: 13px; color: #00ff88; }
            .trades { background: #0e0e16; border: 1px solid #1e1e2e; border-radius: 12px; padding: 18px; margin-bottom: 25px; }
            .trades h2 { color: #888; font-size: 14px; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 15px; }
            .trade-item { padding: 10px 0; border-bottom: 1px solid #1a1a1a; font-size: 13px; color: #aaa; }
            .trade-item:last-child { border-bottom: none; }
            .run-btn { display: block; width: 100%; padding: 16px; background: #00ff88; color: #000; font-size: 16px; font-weight: bold; border: none; border-radius: 12px; cursor: pointer; margin-bottom: 25px; font-family: 'Syne', sans-serif; letter-spacing: 1px; }
            .run-btn:hover { background: #00cc70; }
            .run-btn:disabled { background: #333; color: #666; cursor: not-allowed; }
            .no-trades { color: #444; font-size: 13px; }
            .confidence-high { color: #00ff88; }
            .confidence-medium { color: #ffcc00; }
            .confidence-low { color: #888; }
            .card { background: #0e0e16; border: 1px solid #1e1e2e; border-radius: 12px; padding: 18px; margin-bottom: 25px; }
            .card-title { color: #888; font-size: 14px; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 15px; }
            .input-row { display: grid; gap: 10px; margin-bottom: 15px; }
            .input-row-4 { grid-template-columns: 1fr 1fr 1fr auto; }
            .input-row-3 { grid-template-columns: 1fr 1fr auto; }
            .vulcan-input { width: 100%; padding: 12px; background: #06060a; border: 1px solid #333; border-radius: 8px; color: #fff; font-size: 14px; outline: none; font-family: 'DM Mono', monospace; }
            .vulcan-input:focus { border-color: #00ff8844; box-shadow: 0 0 0 3px #00ff8812; }
            .vulcan-btn-green { padding: 12px 20px; background: #00ff88; color: #000; border: none; border-radius: 8px; font-weight: bold; cursor: pointer; white-space: nowrap; font-family: 'Syne', sans-serif; }
            .vulcan-btn-outline { padding: 12px 20px; background: #0e0e16; color: #00ff88; border: 1px solid #00ff88; border-radius: 8px; font-weight: bold; cursor: pointer; white-space: nowrap; }
            .modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.85); z-index: 999; overflow-y: auto; padding: 20px; }
            .modal-content { background: #0e0e16; border: 1px solid #333; border-radius: 12px; padding: 20px; max-width: 800px; margin: 40px auto; }
            .modal-close { float: right; cursor: pointer; color: #ff4455; font-size: 20px; }
            @media (max-width: 600px) {
                .stocks { grid-template-columns: 1fr; }
                .summary { grid-template-columns: 1fr 1fr; }
                h1 { font-size: 20px; }
                .input-row-4 { grid-template-columns: 1fr 1fr; }
                .input-row-3 { grid-template-columns: 1fr; }
            }
        </style>
    </head>
    <body>
        <div class="topbar">
            <div>
                <h1>⚡ Vulcan</h1>
                <p class="subtitle">Paper trading dashboard</p>
            </div>
            <div class="user-badge">
                <div class="user-pill">👤 <span>{{ username }}</span></div>
                <button class="logout-btn" onclick="window.location.href='/logout'">Sign out</button>
            </div>
        </div>

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

        <div class="card">
            <div class="card-title">🔍 Stock Search</div>
            <input id="tickerInput" type="text" placeholder="Search any stock... (e.g. TSLA, GOOGL)" class="vulcan-input">
            <div id="searchResult" style="margin-top: 12px;"></div>
        </div>

        <button class="run-btn" onclick="getRecommendations()" id="recBtn"
            style="background:#0e0e16; color:#00ff88; border:1px solid #00ff88;">
            ⚡ Get Vulcan Recommendations
        </button>
        <div id="recommendations" style="margin-bottom:25px;"></div>

        <div class="card">
            <div class="card-title">📋 Watchlist Manager</div>
            <div class="input-row input-row-3">
                <input id="addTickerInput" type="text" placeholder="Add stock... (e.g. TSLA)" class="vulcan-input">
                <div></div>
                <button onclick="addStock()" class="vulcan-btn-green">+ Add</button>
            </div>
            <div style="display:flex; flex-wrap:wrap; gap:8px;">
                {% for stock in stocks %}
                <div style="background:#06060a; border:1px solid #333; border-radius:20px; padding:6px 12px; display:flex; align-items:center; gap:8px;">
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
                    <div class="ticker" onclick="showChart('{{ stock.ticker }}')">{{ stock.ticker }}</div>
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

        <div class="card">
            <div class="card-title">💼 My Real Portfolio</div>
            <p style="color:#555; font-size:12px; margin-bottom:15px;">Track your real holdings and get Vulcan signals on each position.</p>
            <div class="input-row input-row-4">
                <input id="holdingTicker" type="text" placeholder="Ticker" class="vulcan-input">
                <input id="holdingShares" type="number" placeholder="Shares" class="vulcan-input">
                <input id="holdingBuyPrice" type="number" placeholder="Avg buy price" class="vulcan-input">
                <button onclick="addHolding()" class="vulcan-btn-green">+ Add</button>
            </div>
            <div id="holdingsList"><p style="color:#444; font-size:13px;">Loading portfolio...</p></div>
        </div>

        <div class="card">
            <div class="card-title">🔔 Price Alerts</div>
            <div class="input-row input-row-4">
                <input id="alertTicker" type="text" placeholder="Ticker" class="vulcan-input">
                <input id="alertTarget" type="number" placeholder="Target price" class="vulcan-input">
                <select id="alertDirection" class="vulcan-input">
                    <option value="above">Rises above</option>
                    <option value="below">Falls below</option>
                </select>
                <button onclick="addAlert()" class="vulcan-btn-green">+ Add</button>
            </div>
            <div id="alertsList" style="margin-bottom:15px;"><p style="color:#444; font-size:13px;">Loading alerts...</p></div>
            <div style="border-top:1px solid #222; padding-top:15px; margin-top:15px;">
                <div class="card-title">📧 Email Alerts</div>
                <div class="input-row input-row-4">
                    <input id="settingsEmail" type="email" placeholder="Your email" class="vulcan-input">
                    <input id="settingsGmailUser" type="email" placeholder="Gmail sender" class="vulcan-input">
                    <input id="settingsGmailPass" type="password" placeholder="App password" class="vulcan-input">
                    <button onclick="saveSettings()" class="vulcan-btn-outline">Save</button>
                </div>
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

        <div class="modal" id="chartModal">
            <div class="modal-content">
                <span class="modal-close" onclick="closeChart()">✕ Close</span>
                <h2 id="chartTitle" style="color:#00ff88; margin-bottom:15px; font-family:'Syne',sans-serif;"></h2>
                <div id="chartContainer"></div>
            </div>
        </div>

        <script>
            function runBot() {
                const btn = document.getElementById('runBtn');
                btn.disabled = true; btn.innerText = '⏳ Running...';
                fetch('/run').then(res => res.json()).then(() => {
                    btn.innerText = '✅ Done! Refreshing...';
                    setTimeout(() => location.reload(), 1500);
                }).catch(() => { btn.innerText = '❌ Error'; btn.disabled = false; });
            }

            document.getElementById('tickerInput').addEventListener('keydown', function(e) {
                if (e.key !== 'Enter') return;
                const ticker = this.value.trim().toUpperCase();
                if (!ticker) return;
                const result = document.getElementById('searchResult');
                result.innerHTML = '<p style="color:#555">Analyzing ' + ticker + '...</p>';
                fetch('/search?ticker=' + ticker).then(res => res.json()).then(data => {
                    if (data.error) {
                        result.innerHTML = '<p style="color:#ff4455">Could not find ' + ticker + '</p>';
                    } else {
                        const confColor = data.confidence === 'High' ? '#00ff88' : data.confidence === 'Medium' ? '#ffcc00' : '#888';
                        result.innerHTML = `<div style="background:#06060a; border:1px solid #1e1e2e; border-radius:12px; padding:18px;">
                            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
                                <span style="font-size:20px; font-weight:bold; cursor:pointer; color:#00ff88;" onclick="showChart('${data.ticker}')">${data.ticker} 📊</span>
                                <span style="padding:4px 10px; border-radius:20px; font-size:13px; ${data.prediction === 1 ? 'background:#00ff8822; color:#00ff88; border:1px solid #00ff8844;' : 'background:#ff445522; color:#ff4455; border:1px solid #ff445544;'}">
                                    ${data.prediction === 1 ? '📈 BUY' : '📉 SELL'}
                                </span>
                            </div>
                            <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px;">
                                <div style="background:#0e0e16; border-radius:8px; padding:8px 12px;"><div style="color:#555; font-size:10px; text-transform:uppercase;">Price</div><div style="font-size:15px; font-weight:bold;">$${data.price}</div></div>
                                <div style="background:#0e0e16; border-radius:8px; padding:8px 12px;"><div style="color:#555; font-size:10px; text-transform:uppercase;">RSI</div><div style="font-size:15px; font-weight:bold; color:${data.rsi > 70 ? '#ff4455' : data.rsi < 30 ? '#00ff88' : '#fff'}">${data.rsi}</div></div>
                                <div style="background:#0e0e16; border-radius:8px; padding:8px 12px; grid-column:span 2;"><div style="color:#555; font-size:10px; text-transform:uppercase;">Confidence</div><div style="font-size:15px; font-weight:bold; color:${confColor}">${data.confidence}</div></div>
                            </div>
                        </div>`;
                    }
                });
            });

            function getRecommendations() {
                const btn = document.getElementById('recBtn');
                const div = document.getElementById('recommendations');
                btn.disabled = true; btn.innerText = '⏳ Scanning market...'; div.innerHTML = '';
                fetch('/recommend').then(res => res.json()).then(data => {
                    btn.disabled = false; btn.innerText = '⚡ Get Vulcan Recommendations';
                    let html = '<div class="card"><div class="card-title">⚡ Recommendations</div>';
                    if (data.buys.length > 0) {
                        html += '<h3 style="color:#00ff88; margin-bottom:10px;">Strong Buys</h3>';
                        data.buys.forEach(s => { html += `<div style="padding:10px; background:#06060a; border-radius:8px; margin-bottom:8px; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;"><span style="font-weight:bold; cursor:pointer; color:#00ff88;" onclick="showChart('${s.ticker}')">${s.ticker} 📊</span><span style="color:#555; font-size:13px;">RSI: ${s.rsi}</span><span style="color:#555; font-size:13px;">$${s.price}</span><span style="color:#00ff88; font-size:13px;">📈 ${s.confidence}</span></div>`; });
                    }
                    if (data.sells.length > 0) {
                        html += '<h3 style="color:#ff4455; margin-top:15px; margin-bottom:10px;">Strong Sells</h3>';
                        data.sells.forEach(s => { html += `<div style="padding:10px; background:#06060a; border-radius:8px; margin-bottom:8px; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;"><span style="font-weight:bold; cursor:pointer; color:#00ff88;" onclick="showChart('${s.ticker}')">${s.ticker} 📊</span><span style="color:#555; font-size:13px;">RSI: ${s.rsi}</span><span style="color:#555; font-size:13px;">$${s.price}</span><span style="color:#ff4455; font-size:13px;">📉 ${s.confidence}</span></div>`; });
                    }
                    html += '</div>'; div.innerHTML = html;
                }).catch(() => { btn.disabled = false; btn.innerText = '⚡ Get Vulcan Recommendations'; });
            }

            function addStock() {
                const ticker = document.getElementById('addTickerInput').value.trim().toUpperCase();
                if (!ticker) return;
                fetch('/add_stock', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ticker}) }).then(() => location.reload());
            }
            function removeStock(ticker) {
                fetch('/remove_stock', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ticker}) }).then(() => location.reload());
            }

            function loadAlerts() {
                fetch('/alerts').then(res => res.json()).then(data => {
                    const div = document.getElementById('alertsList');
                    data.triggered.forEach(alert => {
                        const b = document.createElement('div');
                        b.style = 'background:#00ff8822; border:1px solid #00ff88; border-radius:8px; padding:10px; margin-bottom:8px; color:#00ff88; font-size:13px;';
                        b.innerHTML = `🔔 ${alert.ticker} hit $${alert.current_price} (target: $${alert.target} ${alert.direction})`;
                        document.body.insertBefore(b, document.body.firstChild);
                    });
                    div.innerHTML = data.alerts.length === 0 ? '<p style="color:#444; font-size:13px;">No active alerts.</p>' :
                        data.alerts.map((a, i) => `<div style="padding:10px; background:#06060a; border-radius:8px; margin-bottom:8px; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;"><span style="font-weight:bold;">${a.ticker}</span><span style="color:#555; font-size:13px;">${a.direction} $${a.target}</span><span onclick="removeAlert(${i})" style="color:#ff4455; cursor:pointer;">× Remove</span></div>`).join('');
                });
            }
            function addAlert() {
                const ticker = document.getElementById('alertTicker').value.trim().toUpperCase();
                const target = document.getElementById('alertTarget').value;
                const direction = document.getElementById('alertDirection').value;
                if (!ticker || !target) return;
                fetch('/add_alert', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ticker, target: parseFloat(target), direction}) }).then(() => loadAlerts());
            }
            function removeAlert(i) {
                fetch('/remove_alert', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({index: i}) }).then(() => loadAlerts());
            }
            function saveSettings() {
                fetch('/save_settings', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ email: document.getElementById('settingsEmail').value, gmail_user: document.getElementById('settingsGmailUser').value, gmail_pass: document.getElementById('settingsGmailPass').value }) }).then(() => alert('Settings saved!'));
            }

            function loadHoldings() {
                fetch('/holdings').then(res => res.json()).then(data => {
                    const div = document.getElementById('holdingsList');
                    if (data.length === 0) { div.innerHTML = '<p style="color:#444; font-size:13px;">No holdings added yet.</p>'; return; }
                    let totalValue = 0, totalPnl = 0, html = '';
                    data.forEach((h, i) => {
                        totalValue += h.value; totalPnl += h.pnl;
                        html += `<div style="padding:12px; background:#06060a; border-radius:8px; margin-bottom:8px;">
                            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px; flex-wrap:wrap; gap:8px;">
                                <span style="font-weight:bold; font-size:16px; cursor:pointer; color:#00ff88;" onclick="showChart('${h.ticker}')">${h.ticker} 📊</span>
                                <span style="font-size:13px; color:${h.pnl >= 0 ? '#00ff88' : '#ff4455'};">${h.pnl >= 0 ? '+' : ''}$${h.pnl} (${h.pnl_pct}%)</span>
                                <span onclick="removeHolding(${i})" style="color:#ff4455; cursor:pointer;">× Remove</span>
                            </div>
                            <div style="display:grid; grid-template-columns:repeat(2,1fr); gap:8px; font-size:12px; color:#555;">
                                <div>Shares: <span style="color:#fff;">${h.shares}</span></div>
                                <div>Avg Cost: <span style="color:#fff;">$${h.buy_price}</span></div>
                                <div>Current: <span style="color:#fff;">$${h.current_price}</span></div>
                                <div>Value: <span style="color:#fff;">$${h.value}</span></div>
                            </div>
                            <div style="margin-top:6px; font-size:12px;">Vulcan: <span style="color:${h.signal.includes('BUY') ? '#00ff88' : '#ff4455'}">${h.signal}</span> <span style="color:#555; margin-left:8px;">${h.confidence}</span></div>
                        </div>`;
                    });
                    html += `<div style="padding:12px; border-top:1px solid #222; margin-top:8px; display:flex; justify-content:space-between; flex-wrap:wrap; gap:8px;"><span style="color:#888;">Total Value</span><span style="font-weight:bold;">$${totalValue.toFixed(2)}</span><span style="color:${totalPnl >= 0 ? '#00ff88' : '#ff4455'};">${totalPnl >= 0 ? '+' : ''}$${totalPnl.toFixed(2)} P&L</span></div>`;
                    div.innerHTML = html;
                });
            }
            function addHolding() {
                const ticker = document.getElementById('holdingTicker').value.trim().toUpperCase();
                const shares = document.getElementById('holdingShares').value;
                const buy_price = document.getElementById('holdingBuyPrice').value;
                if (!ticker || !shares || !buy_price) return;
                fetch('/add_holding', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ticker, shares: parseFloat(shares), buy_price: parseFloat(buy_price)}) }).then(() => loadHoldings());
            }
            function removeHolding(i) {
                fetch('/remove_holding', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({index: i}) }).then(() => loadHoldings());
            }

            function showChart(ticker) {
                document.getElementById('chartTitle').innerText = ticker + ' — 6 Month Chart';
                document.getElementById('chartContainer').innerHTML = '<p style="color:#555;">Loading chart...</p>';
                document.getElementById('chartModal').style.display = 'block';
                fetch('/chart?ticker=' + ticker).then(res => res.json()).then(data => {
                    const canvas = document.createElement('canvas');
                    canvas.style = 'width:100%; height:300px;';
                    document.getElementById('chartContainer').innerHTML = '';
                    document.getElementById('chartContainer').appendChild(canvas);
                    new Chart(canvas.getContext('2d'), {
                        type: 'line',
                        data: { labels: data.dates, datasets: [
                            { label: 'Price', data: data.closes, borderColor: '#00ff88', borderWidth: 2, pointRadius: 0, tension: 0.1 },
                            { label: 'MA50', data: data.ma50, borderColor: '#ffcc00', borderWidth: 1.5, pointRadius: 0, borderDash: [5,5] },
                            { label: 'MA200', data: data.ma200, borderColor: '#ff4455', borderWidth: 1.5, pointRadius: 0, borderDash: [5,5] }
                        ]},
                        options: { responsive: true, plugins: { legend: { labels: { color: '#888' } } }, scales: { x: { ticks: { color: '#555', maxTicksLimit: 6 }, grid: { color: '#1a1a1a' } }, y: { ticks: { color: '#555' }, grid: { color: '#1a1a1a' } } } }
                    });
                });
            }
            function closeChart() { document.getElementById('chartModal').style.display = 'none'; }

            loadAlerts();
            loadHoldings();
        </script>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    </body>
    </html>
    """
    return render_template_string(html, stocks=stocks, portfolio=portfolio, total=total,
                                  returns=returns, market=market, username=username)

# ─── All existing routes (protected) ─────────────────────────────────────────

@app.route("/run")
def run():
    if not is_logged_in(): return jsonify({"error": "Unauthorized"}), 401
    run_bot()
    return jsonify({"status": "done"})

@app.route("/search")
def search():
    if not is_logged_in(): return jsonify({"error": "Unauthorized"}), 401
    ticker = request.args.get("ticker", "").upper()
    if not ticker: return jsonify({"error": "No ticker provided"})
    data = analyze_stock(ticker)
    if not data: return jsonify({"error": "Stock not found"})
    return jsonify(data)

@app.route("/recommend")
def recommend():
    if not is_logged_in(): return jsonify({"error": "Unauthorized"}), 401
    SCAN_LIST = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA", "META", "SPY", "QQQ", "AMD", "NFLX", "DIS", "BRK-B", "JPM", "BAC"]
    buys, sells = [], []
    for ticker in SCAN_LIST:
        data = analyze_stock(ticker)
        if data and data["confidence"] == "High":
            (buys if data["prediction"] == 1 else sells).append(data)
    buys.sort(key=lambda x: x["rsi"])
    sells.sort(key=lambda x: x["rsi"], reverse=True)
    return jsonify({"buys": buys, "sells": sells})

@app.route("/chart")
def chart():
    if not is_logged_in(): return jsonify({"error": "Unauthorized"}), 401
    ticker = request.args.get("ticker", "").upper()
    if not ticker: return jsonify({"error": "No ticker"})
    return jsonify(get_chart_data(ticker))

@app.route("/add_stock", methods=["POST"])
def add_stock():
    if not is_logged_in(): return jsonify({"error": "Unauthorized"}), 401
    ticker = request.json.get("ticker", "").upper()
    watchlist = load_watchlist()
    if ticker and ticker not in watchlist:
        watchlist.append(ticker)
        save_watchlist(watchlist)
    return jsonify({"status": "added", "watchlist": watchlist})

@app.route("/remove_stock", methods=["POST"])
def remove_stock():
    if not is_logged_in(): return jsonify({"error": "Unauthorized"}), 401
    ticker = request.json.get("ticker", "").upper()
    watchlist = load_watchlist()
    if ticker in watchlist:
        watchlist.remove(ticker)
        save_watchlist(watchlist)
    return jsonify({"status": "removed", "watchlist": watchlist})

@app.route("/alerts")
def get_alerts():
    if not is_logged_in(): return jsonify({"error": "Unauthorized"}), 401
    triggered = check_alerts()
    settings = load_settings()
    for alert in triggered:
        send_alert_email(alert, settings)
    return jsonify({"alerts": load_alerts(), "triggered": triggered})

@app.route("/add_alert", methods=["POST"])
def add_alert():
    if not is_logged_in(): return jsonify({"error": "Unauthorized"}), 401
    data = request.json
    ticker = data.get("ticker", "").upper()
    target = float(data.get("target", 0))
    direction = data.get("direction", "above")
    if not ticker or not target: return jsonify({"error": "Missing data"})
    alerts = load_alerts()
    alerts.append({"ticker": ticker, "target": target, "direction": direction})
    save_alerts(alerts)
    return jsonify({"status": "added"})

@app.route("/remove_alert", methods=["POST"])
def remove_alert():
    if not is_logged_in(): return jsonify({"error": "Unauthorized"}), 401
    index = request.json.get("index", -1)
    alerts = load_alerts()
    if 0 <= index < len(alerts):
        alerts.pop(index)
        save_alerts(alerts)
    return jsonify({"status": "removed"})

@app.route("/save_settings", methods=["POST"])
def save_settings_route():
    if not is_logged_in(): return jsonify({"error": "Unauthorized"}), 401
    from trader import SETTINGS_FILE
    with open(SETTINGS_FILE, "w") as f:
        json.dump(request.json, f)
    return jsonify({"status": "saved"})

@app.route("/holdings")
def get_holdings():
    if not is_logged_in(): return jsonify({"error": "Unauthorized"}), 401
    holdings = load_holdings()
    enriched = []
    for h in holdings:
        data = analyze_stock(h["ticker"])
        if data:
            cost = h["shares"] * h["buy_price"]
            value = h["shares"] * data["price"]
            pnl = round(value - cost, 2)
            enriched.append({
                **h,
                "current_price": data["price"],
                "value": round(value, 2),
                "pnl": pnl,
                "pnl_pct": round(((value - cost) / cost) * 100, 2),
                "signal": "📈 BUY" if data["prediction"] == 1 else "📉 SELL",
                "confidence": data["confidence"]
            })
    return jsonify(enriched)

@app.route("/add_holding", methods=["POST"])
def add_holding():
    if not is_logged_in(): return jsonify({"error": "Unauthorized"}), 401
    data = request.json
    ticker = data.get("ticker", "").upper()
    shares = float(data.get("shares", 0))
    buy_price = float(data.get("buy_price", 0))
    if not ticker or not shares or not buy_price: return jsonify({"error": "Missing data"})
    holdings = load_holdings()
    holdings.append({"ticker": ticker, "shares": shares, "buy_price": buy_price})
    with open(HOLDINGS_FILE, "w") as f:
        json.dump(holdings, f)
    return jsonify({"status": "added"})

@app.route("/remove_holding", methods=["POST"])
def remove_holding():
    if not is_logged_in(): return jsonify({"error": "Unauthorized"}), 401
    index = request.json.get("index", -1)
    holdings = load_holdings()
    if 0 <= index < len(holdings):
        holdings.pop(index)
        with open(HOLDINGS_FILE, "w") as f:
            json.dump(holdings, f)
    return jsonify({"status": "removed"})

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")