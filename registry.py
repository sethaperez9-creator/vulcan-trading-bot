"""
registry.py — Vulcan Share Registry
Handles: Plaid link, holdings snapshots, email verification,
         hCaptcha validation, duplicate prevention, multi-brokerage per user.
"""

import os, json, hashlib, hmac, time, secrets, smtplib, requests
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from trader import _safe_load, _safe_save

# ── Config from environment / .env ────────────────────────────────────────────
def _load_env_registry():
    import pathlib
    env_path = pathlib.Path(__file__).parent / ".env"
    if not env_path.exists():
        return
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

_load_env_registry()

def _env(key, default=""):
    return os.environ.get(key, default)

PLAID_CLIENT_ID  = _env("PLAID_CLIENT_ID")
PLAID_SECRET     = _env("PLAID_SECRET")
PLAID_ENV        = _env("PLAID_ENV", "sandbox")
HCAPTCHA_SECRET  = _env("HCAPTCHA_SECRET")
GMAIL_USER       = _env("GMAIL_USER")
GMAIL_APP_PW     = _env("GMAIL_APP_PASSWORD")

PLAID_BASE = {
    "sandbox":     "https://sandbox.plaid.com",
    "development": "https://development.plaid.com",
    "production":  "https://production.plaid.com",
}.get(PLAID_ENV, "https://development.plaid.com")

# ── File paths ────────────────────────────────────────────────────────────────
REGISTRY_FILE    = "registry.json"
VERIF_FILE       = "email_verif.json"     # pending verifications
LINKED_FILE      = "linked_accounts.json" # plaid items per user
SNAPSHOTS_FILE   = "snapshots.json"       # verified holding snapshots

def ensure_files():
    for f, d in [(REGISTRY_FILE,{}),(VERIF_FILE,{}),(LINKED_FILE,{}),(SNAPSHOTS_FILE,{})]:
        if not os.path.exists(f):
            _safe_save(f, d)

ensure_files()

# ── hCaptcha verification ─────────────────────────────────────────────────────
def verify_captcha(token: str) -> bool:
    if not token:
        return False
    try:
        r = requests.post("https://hcaptcha.com/siteverify", data={
            "secret":   HCAPTCHA_SECRET,
            "response": token,
        }, timeout=5)
        return r.json().get("success", False)
    except Exception as e:
        print(f"[registry] hCaptcha error: {e}")
        return False

# ── Email verification ────────────────────────────────────────────────────────
def _send_email(to: str, subject: str, body: str):
    """Send email via Gmail SMTP."""
    try:
        msg = MIMEMultipart()
        msg["From"]    = GMAIL_USER
        msg["To"]      = to
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "html"))
        srv = smtplib.SMTP("smtp.gmail.com", 587)
        srv.starttls()
        srv.login(GMAIL_USER, GMAIL_APP_PW.replace(" ", ""))
        srv.send_message(msg)
        srv.quit()
        return True
    except Exception as e:
        print(f"[registry] Email error: {e}")
        return False

def send_verification_email(username: str, email: str, base_url: str) -> bool:
    """Generate a token, store it, and email the user a verification link."""
    token   = secrets.token_urlsafe(32)
    expires = (datetime.now() + timedelta(hours=24)).isoformat()

    verif = _safe_load(VERIF_FILE, {})
    verif[username] = {"email": email, "token": token, "expires": expires, "verified": False}
    _safe_save(VERIF_FILE, verif)

    link = f"{base_url}/verify-email?token={token}&user={username}"
    body = f"""
    <div style="font-family:sans-serif;max-width:480px;margin:auto;background:#0d1220;color:#e2e8f0;padding:32px;border-radius:12px;border:1px solid #1e2d45;">
      <div style="font-size:28px;font-weight:800;background:linear-gradient(135deg,#818cf8,#34d399);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:8px;">⚡ VULCAN</div>
      <h2 style="font-size:18px;margin-bottom:16px;color:#e2e8f0;">Verify your email address</h2>
      <p style="color:#94a3b8;font-size:14px;line-height:1.7;margin-bottom:24px;">
        Hi <strong style="color:#e2e8f0;">{username}</strong>, click the button below to verify your email and activate your Vulcan account.
        This link expires in 24 hours.
      </p>
      <a href="{link}" style="display:inline-block;padding:12px 24px;background:linear-gradient(135deg,#6366f1,#8b5cf6);color:white;text-decoration:none;border-radius:8px;font-weight:700;font-size:14px;">Verify Email →</a>
      <p style="color:#475569;font-size:11px;margin-top:24px;">If you didn't create a Vulcan account, ignore this email.</p>
    </div>
    """
    return _send_email(email, "⚡ Vulcan — Verify your email", body)

def confirm_verification(username: str, token: str) -> bool:
    verif = _safe_load(VERIF_FILE, {})
    entry = verif.get(username)
    if not entry:
        return False
    if entry["token"] != token:
        return False
    if datetime.now() > datetime.fromisoformat(entry["expires"]):
        return False
    entry["verified"] = True
    verif[username] = entry
    _safe_save(VERIF_FILE, verif)
    return True

def is_email_verified(username: str) -> bool:
    verif = _safe_load(VERIF_FILE, {})
    return verif.get(username, {}).get("verified", False)

def get_verified_email(username: str) -> str:
    verif = _safe_load(VERIF_FILE, {})
    return verif.get(username, {}).get("email", "")

def email_already_registered(email: str) -> bool:
    """Prevent duplicate accounts with same email."""
    verif = _safe_load(VERIF_FILE, {})
    email_lower = email.lower().strip()
    for entry in verif.values():
        if entry.get("email", "").lower().strip() == email_lower:
            return True
    return False

# ── Plaid integration ─────────────────────────────────────────────────────────
def _plaid_headers():
    return {"Content-Type": "application/json"}

def _plaid_body(extra: dict) -> dict:
    return {"client_id": PLAID_CLIENT_ID, "secret": PLAID_SECRET, **extra}

def create_link_token(username: str) -> dict:
    """Create a Plaid Link token for the frontend to initialize Link."""
    r = requests.post(
        f"{PLAID_BASE}/link/token/create",
        headers=_plaid_headers(),
        json=_plaid_body({
            "user": {"client_user_id": username},
            "client_name": "Vulcan Trading",
            "products": ["investments"],
            "country_codes": ["US"],
            "language": "en",
        }),
        timeout=10
    )
    data = r.json()
    if "link_token" not in data:
        print(f"[registry] Plaid link token error: {data}")
        return {"error": data.get("error_message", "Plaid error")}
    return {"link_token": data["link_token"]}

def exchange_public_token(username: str, public_token: str, institution_name: str) -> dict:
    """Exchange a Plaid public token for an access token and take a holdings snapshot."""
    # 1. Exchange token
    r = requests.post(
        f"{PLAID_BASE}/item/public_token/exchange",
        headers=_plaid_headers(),
        json=_plaid_body({"public_token": public_token}),
        timeout=10
    )
    ex = r.json()
    if "access_token" not in ex:
        return {"error": ex.get("error_message", "Token exchange failed")}

    access_token = ex["access_token"]
    item_id      = ex["item_id"]

    # 2. Fetch holdings
    r2 = requests.post(
        f"{PLAID_BASE}/investments/holdings/get",
        headers=_plaid_headers(),
        json=_plaid_body({"access_token": access_token}),
        timeout=10
    )
    holdings_data = r2.json()

    if "error" in holdings_data and holdings_data.get("error"):
        err = holdings_data.get("error", {})
        return {"error": err.get("error_message", "Could not fetch holdings")}

    # 3. Parse holdings into clean snapshot
    securities = {s["security_id"]: s for s in holdings_data.get("securities", [])}
    snapshot   = []

    for h in holdings_data.get("holdings", []):
        sec = securities.get(h.get("security_id"), {})
        ticker = sec.get("ticker_symbol") or sec.get("name", "UNKNOWN")
        if not ticker or ticker == "UNKNOWN":
            continue
        snapshot.append({
            "ticker":      ticker.upper(),
            "quantity":    round(h.get("quantity", 0), 4),
            "value":       round(h.get("institution_value", 0), 2),
            "cost_basis":  round(h.get("cost_basis", 0), 2) if h.get("cost_basis") else None,
        })

    # 4. Store linked account (store access_token encrypted-ish — in production use a vault)
    linked = _safe_load(LINKED_FILE, {})
    if username not in linked:
        linked[username] = []

    # Check if institution already linked
    existing_ids = [a["item_id"] for a in linked[username]]
    if item_id not in existing_ids:
        linked[username].append({
            "item_id":          item_id,
            "institution":      institution_name,
            "access_token":     access_token,  # TODO: encrypt in production
            "linked_at":        datetime.now().isoformat(),
        })
    _safe_save(LINKED_FILE, linked)

    # 5. Save snapshot
    snap_ts = datetime.now().isoformat()
    snap_hash = hashlib.sha256(
        json.dumps(snapshot, sort_keys=True).encode() + snap_ts.encode()
    ).hexdigest()[:16]

    snaps = _safe_load(SNAPSHOTS_FILE, {})
    if username not in snaps:
        snaps[username] = []

    snaps[username].append({
        "institution": institution_name,
        "item_id":     item_id,
        "timestamp":   snap_ts,
        "hash":        snap_hash,
        "holdings":    snapshot,
    })
    _safe_save(SNAPSHOTS_FILE, snaps)

    # 6. Update public registry with verified counts
    _update_registry_from_snapshot(username, snapshot, institution_name, snap_ts, snap_hash)

    return {"success": True, "holdings": snapshot, "institution": institution_name, "hash": snap_hash}

def refresh_holdings(username: str) -> dict:
    """Re-fetch holdings for all linked accounts and update snapshots."""
    linked = _safe_load(LINKED_FILE, {})
    accounts = linked.get(username, [])
    if not accounts:
        return {"error": "No linked accounts"}

    results = []
    for acct in accounts:
        r = requests.post(
            f"{PLAID_BASE}/investments/holdings/get",
            headers=_plaid_headers(),
            json=_plaid_body({"access_token": acct["access_token"]}),
            timeout=10
        )
        hdata = r.json()
        if "holdings" not in hdata:
            continue

        securities = {s["security_id"]: s for s in hdata.get("securities", [])}
        snapshot   = []
        for h in hdata.get("holdings", []):
            sec    = securities.get(h.get("security_id"), {})
            ticker = sec.get("ticker_symbol") or sec.get("name", "UNKNOWN")
            if not ticker or ticker == "UNKNOWN":
                continue
            snapshot.append({
                "ticker":     ticker.upper(),
                "quantity":   round(h.get("quantity", 0), 4),
                "value":      round(h.get("institution_value", 0), 2),
                "cost_basis": round(h.get("cost_basis", 0), 2) if h.get("cost_basis") else None,
            })

        snap_ts   = datetime.now().isoformat()
        snap_hash = hashlib.sha256(
            json.dumps(snapshot, sort_keys=True).encode() + snap_ts.encode()
        ).hexdigest()[:16]

        snaps = _safe_load(SNAPSHOTS_FILE, {})
        if username not in snaps:
            snaps[username] = []
        snaps[username].append({
            "institution": acct["institution"],
            "item_id":     acct["item_id"],
            "timestamp":   snap_ts,
            "hash":        snap_hash,
            "holdings":    snapshot,
        })
        _safe_save(SNAPSHOTS_FILE, snaps)
        _update_registry_from_snapshot(username, snapshot, acct["institution"], snap_ts, snap_hash)
        results.append({"institution": acct["institution"], "holdings": snapshot})

    return {"success": True, "accounts": results}

def get_user_linked_accounts(username: str) -> list:
    linked = _safe_load(LINKED_FILE, {})
    accounts = linked.get(username, [])
    # Return without access tokens
    return [{"institution": a["institution"], "item_id": a["item_id"], "linked_at": a["linked_at"]}
            for a in accounts]

def get_user_snapshots(username: str) -> list:
    snaps = _safe_load(SNAPSHOTS_FILE, {})
    user_snaps = snaps.get(username, [])
    # Return most recent snapshot per institution
    seen = {}
    for s in reversed(user_snaps):
        iid = s["item_id"]
        if iid not in seen:
            seen[iid] = s
    return list(seen.values())

def _update_registry_from_snapshot(username, snapshot, institution, timestamp, snap_hash):
    """Write verified holdings into the public registry."""
    reg = _safe_load(REGISTRY_FILE, {})

    # First clear old entries from this user for this institution
    for ticker in list(reg.keys()):
        holders = reg[ticker].get("holders", {})
        # Remove entries matching this user+institution
        to_del = [k for k in holders if k.startswith(f"{username}::{institution}")]
        for k in to_del:
            del holders[k]
        reg[ticker]["total_shares"] = sum(v["shares"] for v in holders.values())
        if not holders:
            del reg[ticker]

    # Add new snapshot entries
    for h in snapshot:
        ticker = h["ticker"]
        if ticker not in reg:
            reg[ticker] = {"total_shares": 0, "holders": {}}
        key = f"{username}::{institution}"
        reg[ticker]["holders"][key] = {
            "username":    username,
            "institution": institution,
            "shares":      h["quantity"],
            "value":       h["value"],
            "verified":    True,
            "timestamp":   timestamp,
            "hash":        snap_hash,
        }
        reg[ticker]["total_shares"] = sum(v["shares"] for v in reg[ticker]["holders"].values())

    _safe_save(REGISTRY_FILE, reg)

# ── Public registry read ───────────────────────────────────────────────────────
def get_registry_with_flags() -> list:
    reg    = _safe_load(REGISTRY_FILE, {})
    result = []
    for ticker, data in reg.items():
        try:
            info         = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}",
                                        headers={"User-Agent":"Mozilla/5.0"}, timeout=5).json()
            float_shares = (info.get("chart",{}).get("result",[{}])[0]
                               .get("summaryDetail",{}).get("floatShares",{}).get("raw",0))
        except:
            float_shares = 0

        community = data.get("total_shares", 0)
        holders   = data.get("holders", {})
        n_holders = len(holders)
        verified  = all(v.get("verified", False) for v in holders.values())

        flag, reason = False, ""
        if float_shares > 0:
            pct = (community / float_shares) * 100
            if pct > 0.1:
                flag   = True
                reason = f"Community holds {pct:.4f}% of float"

        result.append({
            "ticker":           ticker,
            "community_shares": round(community, 2),
            "float_shares":     float_shares,
            "n_holders":        n_holders,
            "verified":         verified,
            "flagged":          flag,
            "flag_reason":      reason,
            "holders":          [
                {
                    "institution": v.get("institution", "Manual"),
                    "shares":      v.get("shares", 0),
                    "verified":    v.get("verified", False),
                    "timestamp":   v.get("timestamp",""),
                    "hash":        v.get("hash",""),
                }
                for v in holders.values()
            ],
        })
    return sorted(result, key=lambda x: x["community_shares"], reverse=True)