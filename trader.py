import yfinance as yf
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
import json, os, math, smtplib
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

WATCHLIST_FILE = "watchlist.json"
ALERTS_FILE    = "alerts.json"
SETTINGS_FILE  = "settings.json"
REGISTRY_FILE  = "registry.json"
PORTFOLIOS_DIR = "portfolios"

def ensure_dirs():
    os.makedirs(PORTFOLIOS_DIR, exist_ok=True)

# ── Safe JSON loader — handles corrupted / UTF-16 / empty files ───────────────
def _safe_load(path, default):
    if not os.path.exists(path):
        return default
    try:
        # Try UTF-8 first
        with open(path, "r", encoding="utf-8") as f:
            text = f.read().strip()
        if not text:
            return default
        return json.loads(text)
    except (UnicodeDecodeError, json.JSONDecodeError):
        pass
    try:
        # Fallback: UTF-16 (BOM = 0xff 0xfe)
        with open(path, "r", encoding="utf-16") as f:
            text = f.read().strip()
        if not text:
            return default
        return json.loads(text)
    except Exception:
        pass
    # File is unreadable — delete and return default so app keeps running
    print(f"[vulcan] WARNING: {path} is corrupt, resetting to default.")
    os.remove(path)
    return default

def _safe_save(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)

# ── Watchlist ─────────────────────────────────────────────────────────────────
def load_watchlist():
    return _safe_load(WATCHLIST_FILE, ["SPY","NVDA","AAPL","TSLA","MSFT"])

def save_watchlist(wl):
    _safe_save(WATCHLIST_FILE, wl)

# ── Per-user portfolio ────────────────────────────────────────────────────────
def get_portfolio_path(username):
    ensure_dirs()
    return os.path.join(PORTFOLIOS_DIR, f"{username}.json")

def load_portfolio(username):
    return _safe_load(get_portfolio_path(username),
                      {"cash":10000,"starting_cash":10000,"positions":{},"trades":[]})

def save_portfolio(username, portfolio):
    _safe_save(get_portfolio_path(username), portfolio)

def set_starting_cash(username, amount):
    p = load_portfolio(username)
    p.update({"cash":amount,"starting_cash":amount,"positions":{},"trades":[]})
    save_portfolio(username, p)

# ── Alerts ────────────────────────────────────────────────────────────────────
def load_alerts():
    return _safe_load(ALERTS_FILE, [])

def save_alerts(alerts):
    _safe_save(ALERTS_FILE, alerts)

# ── Settings ──────────────────────────────────────────────────────────────────
def load_settings():
    return _safe_load(SETTINGS_FILE, {"email":"","gmail_user":"","gmail_pass":""})

def save_settings(data):
    _safe_save(SETTINGS_FILE, data)

def send_alert_email(alert, settings):
    if not settings.get("email") or not settings.get("gmail_user") or not settings.get("gmail_pass"):
        return
    try:
        msg = MIMEMultipart()
        msg["From"]    = settings["gmail_user"]
        msg["To"]      = settings["email"]
        msg["Subject"] = f"Vulcan Alert — {alert['ticker']} hit ${alert['current_price']}"
        msg.attach(MIMEText(
            f"Alert triggered!\n\nStock: {alert['ticker']}\n"
            f"Target: ${alert['target']} ({alert['direction']})\n"
            f"Current: ${alert['current_price']}\n\n— Vulcan", "plain"))
        srv = smtplib.SMTP("smtp.gmail.com", 587)
        srv.starttls()
        srv.login(settings["gmail_user"], settings["gmail_pass"])
        srv.send_message(msg)
        srv.quit()
    except Exception as e:
        print(f"[vulcan] Email error: {e}")

def check_alerts():
    alerts = load_alerts()
    triggered, remaining = [], []
    for a in alerts:
        try:
            price = round(yf.Ticker(a["ticker"]).history(period="1d")["Close"].iloc[-1], 2)
            hit = (a["direction"]=="above" and price >= a["target"]) or \
                  (a["direction"]=="below" and price <= a["target"])
            (triggered if hit else remaining).append({**a, "current_price": price} if hit else a)
        except:
            remaining.append(a)
    save_alerts(remaining)
    return triggered

# ── Registry ──────────────────────────────────────────────────────────────────
def load_registry():
    return _safe_load(REGISTRY_FILE, {})

def save_registry(r):
    _safe_save(REGISTRY_FILE, r)

def update_registry(username, ticker, shares, buy_price, action="add"):
    reg = load_registry()
    if ticker not in reg:
        reg[ticker] = {"total_shares":0,"holders":{}}
    if action == "add":
        reg[ticker]["holders"][username] = {"shares":shares,"buy_price":buy_price,"added":datetime.now().isoformat()}
    elif action == "remove":
        reg[ticker]["holders"].pop(username, None)
    reg[ticker]["total_shares"] = sum(v["shares"] for v in reg[ticker]["holders"].values())
    if not reg[ticker]["holders"]:
        del reg[ticker]
    save_registry(reg)

def get_registry_with_flags():
    reg = load_registry()
    result = []
    for ticker, data in reg.items():
        try:
            info = yf.Ticker(ticker).info
            float_shares = info.get("floatShares") or info.get("sharesOutstanding") or 0
            community    = data["total_shares"]
            holders      = len(data["holders"])
            flag, reason = False, ""
            if float_shares > 0:
                pct = (community / float_shares) * 100
                if pct > 0.01:
                    flag = True
                    reason = f"Community holds {pct:.4f}% of float"
            counts = [v["shares"] for v in data["holders"].values()]
            if len(counts) > 2 and len(counts) != len(set(counts)):
                flag = True
                reason = "Duplicate share counts detected"
            result.append({"ticker":ticker,"community_shares":community,"float_shares":float_shares,
                           "holders":holders,"flagged":flag,"flag_reason":reason})
        except:
            result.append({"ticker":ticker,"community_shares":data["total_shares"],"float_shares":0,
                           "holders":len(data["holders"]),"flagged":False,"flag_reason":""})
    return result

# ── Stock analysis ────────────────────────────────────────────────────────────
def analyze_stock(ticker):
    try:
        h = yf.Ticker(ticker).history(period="2y")
        if h.empty or len(h) < 50:
            return None
        h["MA20"]   = h["Close"].rolling(20).mean()
        h["MA50"]   = h["Close"].rolling(50).mean()
        h["MA200"]  = h["Close"].rolling(200).mean()
        delta       = h["Close"].diff()
        rs          = delta.where(delta>0,0).rolling(14).mean() / (-delta.where(delta<0,0).rolling(14).mean())
        h["RSI"]    = 100 - (100/(1+rs))
        ema12       = h["Close"].ewm(span=12).mean()
        ema26       = h["Close"].ewm(span=26).mean()
        h["MACD"]   = ema12 - ema26
        h["Signal"] = h["MACD"].ewm(span=9).mean()
        h["BB_mid"] = h["Close"].rolling(20).mean()
        h["BB_std"] = h["Close"].rolling(20).std()
        h["BB_up"]  = h["BB_mid"] + 2*h["BB_std"]
        h["BB_dn"]  = h["BB_mid"] - 2*h["BB_std"]
        h["Target"] = (h["Close"].shift(-1) > h["Close"]).astype(int)
        h.dropna(inplace=True)

        feats = ["Close","MA20","MA50","MA200","RSI","MACD","Signal","BB_up","BB_dn"]
        X, y  = h[feats], h["Target"]
        Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, random_state=42)
        model = RandomForestClassifier(n_estimators=150, random_state=42)
        model.fit(Xtr, ytr)

        latest     = pd.DataFrame([h[feats].iloc[-1]], columns=feats)
        prediction = int(model.predict(latest)[0])
        proba      = float(model.predict_proba(latest)[0][1])

        rsi    = round(float(h["RSI"].iloc[-1]),   2)
        ma20   = round(float(h["MA20"].iloc[-1]),   2)
        ma50   = round(float(h["MA50"].iloc[-1]),   2)
        ma200  = round(float(h["MA200"].iloc[-1]),  2)
        macd   = round(float(h["MACD"].iloc[-1]),   4)
        sig    = round(float(h["Signal"].iloc[-1]), 4)
        bb_up  = round(float(h["BB_up"].iloc[-1]),  2)
        bb_dn  = round(float(h["BB_dn"].iloc[-1]),  2)
        ma_gap = abs(ma50-ma200)/ma200*100

        score = 0
        if proba > 0.65: score += 2
        elif proba > 0.55: score += 1
        if rsi < 35: score += 2
        elif rsi < 45: score += 1
        if ma50 > ma200: score += 1
        if macd > sig: score += 1
        if ma_gap > 3: score += 1

        confidence = "High" if score >= 5 else "Medium" if score >= 3 else "Low"
        prev       = round(float(h["Close"].iloc[-2]), 2)
        price      = round(float(h["Close"].iloc[-1]), 2)
        chg        = round(((price-prev)/prev)*100, 2)

        return {"ticker":ticker,"price":price,"prev_close":prev,"change_pct":chg,
                "rsi":rsi,"ma20":ma20,"ma50":ma50,"ma200":ma200,
                "macd":macd,"signal_line":sig,"bb_up":bb_up,"bb_dn":bb_dn,
                "prediction":prediction,"proba":round(proba,3),"confidence":confidence}
    except Exception as e:
        print(f"[vulcan] analyze_stock({ticker}): {e}")
        return None

# ── Chart data (OHLCV + MAs + Bollinger) ─────────────────────────────────────
PERIOD_MAP = {
    "1mo":  ("3mo",  None),
    "3mo":  ("6mo",  None),
    "6mo":  ("1y",   None),
    "ytd":  ("ytd",  None),
    "1y":   ("2y",   252),
    "5y":   ("5y",   None),
    "max":  ("max",  None),
}

def get_chart_data(ticker, period="6mo"):
    yf_period, tail = PERIOD_MAP.get(period, ("1y", None))
    h = yf.Ticker(ticker).history(period=yf_period)
    h["MA20"]  = h["Close"].rolling(20).mean()
    h["MA50"]  = h["Close"].rolling(50).mean()
    h["MA200"] = h["Close"].rolling(200).mean()
    h = h.dropna(subset=["MA20"])
    if tail:
        h = h.tail(tail)

    def safe(v):
        try:
            f = float(v)
            return None if math.isnan(f) else round(f, 2)
        except: return None

    candles = [{"time":str(ts.date()),"open":safe(r["Open"]),"high":safe(r["High"]),
                "low":safe(r["Low"]),"close":safe(r["Close"]),"volume":int(r["Volume"])}
               for ts,r in h.iterrows()]
    ma20  = [{"time":str(ts.date()),"value":safe(r["MA20"])}  for ts,r in h.iterrows() if safe(r["MA20"])]
    ma50  = [{"time":str(ts.date()),"value":safe(r["MA50"])}  for ts,r in h.iterrows() if safe(r["MA50"])]
    ma200 = [{"time":str(ts.date()),"value":safe(r["MA200"])} for ts,r in h.iterrows() if safe(r["MA200"])]
    vols  = [{"time":str(ts.date()),"value":int(r["Volume"]),
              "color":"rgba(99,102,241,.5)" if r["Close"]>=r["Open"] else "rgba(139,92,246,.35)"}
             for ts,r in h.iterrows()]
    return {"candles":candles,"ma20":ma20,"ma50":ma50,"ma200":ma200,"volumes":vols}

# ── Bot — autonomous trading ──────────────────────────────────────────────────
STRATEGIES = {
    "aggressive":  {"alloc":{"High":0.30,"Medium":0.22,"Low":0.15},"max_pos":6,"rsi_sell":80},
    "balanced":    {"alloc":{"High":0.22,"Medium":0.16,"Low":0.10},"max_pos":5,"rsi_sell":75},
    "conservative":{"alloc":{"High":0.15,"Medium":0.10,"Low":0.06},"max_pos":4,"rsi_sell":70},
}

# Extended scan list — bot always scans these regardless of watchlist
BOT_SCAN = [
    # Tech
    "AAPL","MSFT","NVDA","TSLA","AMZN","GOOGL","META","AMD","NFLX",
    "INTC","MU","QCOM","AVGO","CRM","ORCL","IBM","SNOW","PLTR","NET",
    # Finance
    "JPM","BAC","GS","MS","WFC","C","AXP","BLK","V","MA",
    # Consumer
    "DIS","UBER","SHOP","PYPL","NKE","SBUX","MCD","TGT","WMT","COST",
    # Health
    "JNJ","PFE","MRNA","ABBV","UNH","CVS","LLY","TMO",
    # Energy
    "XOM","CVX","COP","SLB",
    # ETFs
    "SPY","QQQ","IWM","XLF","XLK","XLE","XLV",
]

def run_bot(username, strategy="balanced"):
    cfg       = STRATEGIES.get(strategy, STRATEGIES["balanced"])
    portfolio = load_portfolio(username)
    date      = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Merge watchlist + built-in scan list, deduplicated
    watchlist = load_watchlist()
    import random
    full_scan = list(dict.fromkeys(watchlist + BOT_SCAN))
    # Always include watchlist, randomly sample from the rest
    extra = [t for t in full_scan if t not in watchlist]
    random.shuffle(extra)
    scan = watchlist + extra[:15]  # cap at 15 + watchlist stocks per run

    open_positions = sum(1 for p in portfolio["positions"].values() if p.get("shares", 0) > 0)
    cooldowns = portfolio.get("cooldowns", {})
    now = datetime.now()
    # Clear expired cooldowns (24 hour cooldown)
    cooldowns = {t: ts for t, ts in cooldowns.items() 
                 if (now - datetime.fromisoformat(ts)).total_seconds() < 86400}
    portfolio["cooldowns"] = cooldowns

    for ticker in scan:
        data = analyze_stock(ticker)
        if not data:
            continue

        price      = data["price"]
        proba      = data["proba"]
        prediction = data["prediction"]
        rsi        = data["rsi"]
        macd       = data["macd"]
        sig        = data["signal_line"]
        confidence = data["confidence"]
        position   = portfolio["positions"].get(ticker, {"shares": 0, "buy_price": 0})
        has_pos    = position.get("shares", 0) > 0

        # ── SELL logic ────────────────────────────────────────────────────────
        if has_pos:
            buy_price = position["buy_price"]
            pnl_pct   = ((price - buy_price) / buy_price) * 100
            # Sell if: prediction flipped down, OR RSI overbought, OR stop-loss -8%, OR take-profit +15%
            should_sell = (
                prediction == 0
                or rsi > cfg["rsi_sell"]
                or pnl_pct <= -8.0
                or pnl_pct >= 15.0
            )
            if should_sell:
                rev    = round(position["shares"] * price, 2)
                profit = round((price - buy_price) * position["shares"], 2)
                portfolio["cash"] = round(portfolio["cash"] + rev, 2)
                portfolio["positions"][ticker] = {"shares": 0, "buy_price": 0}
                open_positions -= 1
                portfolio["trades"].append({
                    "action": "SELL", "ticker": ticker, "date": date,
                    "price": price, "shares": position["shares"],
                    "total": rev, "profit": profit,
                    "reason": "stop-loss" if pnl_pct<=-8 else "take-profit" if pnl_pct>=15 else "signal",
                    "proba": proba
                })
                portfolio["cooldowns"][ticker] = datetime.now().isoformat()
            continue  # don't try to buy something we already hold

        # ── BUY logic ─────────────────────────────────────────────────────────
        if open_positions >= cfg["max_pos"]:
            continue  # portfolio full

        if portfolio["cash"] < price:
            continue  # can't afford even 1 share
        if ticker in cooldowns:
            continue
        # Buy signal: prediction==1 AND any supporting indicator
        # Deliberately loose — at least ONE indicator must agree
        signal_count = sum([
            prediction == 1,
            proba > 0.50,          # model leans up
            rsi < 55,              # not overbought
            macd > sig,            # MACD bullish crossover
            data["ma20"] > data["ma50"] or data["ma50"] > data["ma200"],  # trend up
        ])

        should_buy = signal_count >= 2  # just 2 of 5 signals needed

        if should_buy:
            alloc_pct = cfg["alloc"].get(confidence, 0.10)
            alloc     = portfolio["cash"] * alloc_pct
            shares    = max(1, int(alloc / price))  # buy at least 1 share
            # Cap so we never spend more than we have
            if shares * price > portfolio["cash"]:
                shares = int(portfolio["cash"] / price)
            if shares < 1:
                continue

            cost = round(shares * price, 2)
            portfolio["cash"] = round(portfolio["cash"] - cost, 2)
            portfolio["positions"][ticker] = {"shares": shares, "buy_price": price}
            open_positions += 1
            portfolio["trades"].append({
                "action": "BUY", "ticker": ticker, "date": date,
                "price": price, "shares": shares, "total": cost,
                "confidence": confidence, "proba": proba, "signals": signal_count
            })

    # Snapshot portfolio value for graph
    total_value = portfolio["cash"] + sum(
        pos["shares"] * pos["buy_price"]
        for pos in portfolio["positions"].values()
        if pos.get("shares", 0) > 0
    )
    if "history" not in portfolio:
        portfolio["history"] = []
    portfolio["history"].append({
        "time": datetime.now().strftime("%Y-%m-%d"),
        "value": round(total_value, 2)
    })
    # Keep last 365 snapshots
    portfolio["history"] = portfolio["history"][-365:]

    save_portfolio(username, portfolio)
    return portfolio