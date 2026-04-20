from flask import Flask, render_template_string, jsonify, request, session, redirect, url_for
import yfinance as yf
import json, os, hashlib, secrets
from datetime import datetime
from trader import (analyze_stock, run_bot, get_chart_data, load_watchlist, save_watchlist,
    load_alerts, save_alerts, check_alerts, send_alert_email, load_settings,
    load_portfolio, save_portfolio, set_starting_cash,
    load_registry, get_registry_with_flags, update_registry, ensure_dirs)

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)
USERS_FILE = "users.json"
HOLDINGS_FILE = "holdings.json"
ensure_dirs()

def hash_pw(pw): return hashlib.sha256(pw.encode()).hexdigest()
def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE) as f: return json.load(f)
    return {}
def save_users(u):
    with open(USERS_FILE,"w") as f: json.dump(u,f)
def logged_in(): return "username" in session
def me(): return session.get("username","")
def load_holdings():
    if os.path.exists(HOLDINGS_FILE):
        with open(HOLDINGS_FILE) as f: return json.load(f)
    return []


CSS = """
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0;}
:root{
--bg:#080b14;--surface:#0d1220;--surface2:#111827;--border:#1e2d45;--border2:#243552;
--indigo:#6366f1;--indigo-l:#818cf8;--indigo-d:#3730a3;--violet:#8b5cf6;--cyan:#22d3ee;
--vir:#2d9e7a;--vir-l:#34d399;--vir-ll:#6ee7b7;--cel:#a7f3d0;--pine:#166553;
--danger:#f43f5e;--warn:#f59e0b;
--text:#e2e8f0;--text2:#94a3b8;--text3:#475569;
--sidebar-w:230px;--radius:14px;--radius-sm:8px;
}
html,body{height:100%;}
body{font-family:'Outfit',sans-serif;background:var(--bg);color:var(--text);display:flex;min-height:100vh;overflow-x:hidden;}
.sidebar{width:var(--sidebar-w);min-height:100vh;background:var(--surface);border-right:1px solid var(--border);display:flex;flex-direction:column;position:fixed;left:0;top:0;bottom:0;z-index:100;transition:transform .3s ease;}
.sidebar-logo{padding:28px 20px 20px;border-bottom:1px solid var(--border);display:flex;align-items:center;gap:10px;}
.logo-mark{width:36px;height:36px;background:linear-gradient(135deg,var(--indigo),var(--vir));border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:18px;flex-shrink:0;box-shadow:0 0 20px rgba(99,102,241,.4);}
.logo-text{font-size:20px;font-weight:800;letter-spacing:-.5px;background:linear-gradient(135deg,var(--indigo-l),var(--vir-l));-webkit-background-clip:text;-webkit-text-fill-color:transparent;}
.logo-sub{font-size:9px;color:var(--text3);text-transform:uppercase;letter-spacing:2px;margin-top:1px;-webkit-text-fill-color:var(--text3);}
.sidebar-nav{flex:1;padding:16px 12px;display:flex;flex-direction:column;gap:2px;}
.nav-section{font-size:9px;text-transform:uppercase;letter-spacing:2px;color:var(--text3);padding:12px 8px 6px;}
.nav-item{display:flex;align-items:center;gap:10px;padding:10px 12px;border-radius:var(--radius-sm);color:var(--text2);text-decoration:none;font-size:14px;font-weight:500;transition:all .15s;position:relative;cursor:pointer;border:none;background:none;width:100%;text-align:left;font-family:'Outfit',sans-serif;}
.nav-item:hover{background:rgba(99,102,241,.08);color:var(--text);}
.nav-item.active{background:linear-gradient(135deg,rgba(99,102,241,.15),rgba(45,158,122,.1));color:var(--indigo-l);border:1px solid rgba(99,102,241,.2);}
.nav-item.active::before{content:'';position:absolute;left:0;top:20%;bottom:20%;width:3px;background:linear-gradient(180deg,var(--indigo),var(--vir));border-radius:0 3px 3px 0;}
.nav-icon{font-size:16px;width:20px;text-align:center;}
.sidebar-footer{padding:16px 12px;border-top:1px solid var(--border);}
.user-card{display:flex;align-items:center;gap:10px;padding:10px 12px;background:var(--surface2);border-radius:var(--radius-sm);border:1px solid var(--border);}
.user-avatar{width:32px;height:32px;background:linear-gradient(135deg,var(--indigo-d),var(--pine));border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:700;color:white;flex-shrink:0;}
.user-name{font-size:13px;font-weight:600;}
.user-role{font-size:10px;color:var(--text3);}
.logout-link{display:flex;align-items:center;gap:8px;padding:8px 12px;color:var(--text3);font-size:12px;text-decoration:none;border-radius:var(--radius-sm);margin-top:6px;transition:all .15s;}
.logout-link:hover{color:var(--danger);background:rgba(244,63,94,.08);}
.main{margin-left:var(--sidebar-w);flex:1;display:flex;flex-direction:column;min-height:100vh;position:relative;z-index:1;}
.market-bar{display:flex;gap:0;border-bottom:1px solid var(--border);overflow-x:auto;scrollbar-width:none;}
.market-bar::-webkit-scrollbar{display:none;}
.market-item{padding:10px 20px;display:flex;align-items:center;gap:10px;border-right:1px solid var(--border);flex-shrink:0;font-size:13px;}
.market-name{color:var(--text3);font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:1px;}
.market-price{font-weight:700;font-family:'JetBrains Mono',monospace;}
.page-header{padding:32px 36px 24px;border-bottom:1px solid var(--border);background:rgba(13,18,32,.8);backdrop-filter:blur(12px);position:sticky;top:0;z-index:50;}
.page-title{font-size:26px;font-weight:800;letter-spacing:-.5px;background:linear-gradient(135deg,var(--text) 0%,var(--text2) 100%);-webkit-background-clip:text;-webkit-text-fill-color:transparent;}
.page-subtitle{font-size:13px;color:var(--text3);margin-top:3px;}
.page-body{padding:32px 36px;flex:1;}
.card{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:24px;position:relative;overflow:hidden;}
.card::before{content:'';position:absolute;top:0;left:0;right:0;height:1px;background:linear-gradient(90deg,transparent,rgba(99,102,241,.3),transparent);}
.card-title{font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:2px;color:var(--text3);margin-bottom:16px;}
.stat-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:16px;margin-bottom:28px;}
.stat-card{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:20px;position:relative;overflow:hidden;transition:border-color .2s,transform .2s;}
.stat-card:hover{border-color:var(--border2);transform:translateY(-1px);}
.stat-label{font-size:11px;color:var(--text3);text-transform:uppercase;letter-spacing:1.5px;font-weight:500;}
.stat-value{font-size:28px;font-weight:800;margin-top:6px;letter-spacing:-1px;font-family:'JetBrains Mono',monospace;}
.stat-sub{font-size:12px;color:var(--text3);margin-top:4px;}
.up{color:var(--vir-l);}.down{color:var(--danger);}.neutral{color:var(--indigo-l);}
.btn{display:inline-flex;align-items:center;gap:8px;padding:11px 20px;border-radius:var(--radius-sm);font-size:14px;font-weight:600;cursor:pointer;border:none;font-family:'Outfit',sans-serif;transition:all .15s;text-decoration:none;}
.btn-primary{background:linear-gradient(135deg,var(--indigo),var(--violet));color:white;box-shadow:0 4px 16px rgba(99,102,241,.3);}
.btn-primary:hover{transform:translateY(-1px);box-shadow:0 6px 20px rgba(99,102,241,.4);}
.btn-green{background:linear-gradient(135deg,var(--pine),var(--vir));color:white;box-shadow:0 4px 16px rgba(45,158,122,.3);}
.btn-green:hover{transform:translateY(-1px);}
.btn-outline{background:transparent;color:var(--indigo-l);border:1px solid var(--border2);}
.btn-outline:hover{background:rgba(99,102,241,.08);border-color:var(--indigo);}
.btn-danger{background:rgba(244,63,94,.1);color:var(--danger);border:1px solid rgba(244,63,94,.2);}
.btn-danger:hover{background:rgba(244,63,94,.2);}
.btn:disabled{opacity:.4;cursor:not-allowed;transform:none!important;}
.btn-block{width:100%;justify-content:center;}
.input{width:100%;padding:11px 14px;background:var(--surface2);border:1px solid var(--border);border-radius:var(--radius-sm);color:var(--text);font-size:14px;font-family:'Outfit',sans-serif;outline:none;transition:border-color .15s,box-shadow .15s;}
.input:focus{border-color:rgba(99,102,241,.5);box-shadow:0 0 0 3px rgba(99,102,241,.1);}
.input::placeholder{color:var(--text3);}
.form-label{font-size:11px;text-transform:uppercase;letter-spacing:1.5px;color:var(--text3);margin-bottom:6px;font-weight:600;display:block;}
.stock-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:16px;}
.stock-card{background:var(--surface);border-radius:var(--radius);padding:20px;border:1px solid var(--border);transition:all .2s;cursor:pointer;position:relative;overflow:hidden;}
.stock-card:hover{border-color:var(--border2);transform:translateY(-2px);box-shadow:0 8px 32px rgba(0,0,0,.3);}
.stock-card.bull{border-top:2px solid var(--vir);}
.stock-card.bear{border-top:2px solid var(--danger);}
.stock-header{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:14px;}
.stock-ticker{font-size:22px;font-weight:800;letter-spacing:-.5px;}
.badge{font-size:11px;font-weight:700;padding:4px 10px;border-radius:20px;letter-spacing:.5px;text-transform:uppercase;}
.badge-bull{background:rgba(52,211,153,.12);color:var(--vir-l);border:1px solid rgba(52,211,153,.2);}
.badge-bear{background:rgba(244,63,94,.12);color:var(--danger);border:1px solid rgba(244,63,94,.2);}
.badge-high{background:rgba(99,102,241,.12);color:var(--indigo-l);border:1px solid rgba(99,102,241,.2);}
.badge-warn{background:rgba(245,158,11,.12);color:var(--warn);border:1px solid rgba(245,158,11,.2);}
.stock-price{font-size:26px;font-weight:800;font-family:'JetBrains Mono',monospace;letter-spacing:-1px;}
.stock-change{font-size:12px;margin-top:2px;font-family:'JetBrains Mono',monospace;}
.stock-stats{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:14px;}
.mini-stat{background:var(--surface2);border-radius:6px;padding:8px 10px;}
.mini-label{font-size:9px;text-transform:uppercase;letter-spacing:1px;color:var(--text3);}
.mini-value{font-size:14px;font-weight:700;font-family:'JetBrains Mono',monospace;margin-top:2px;}
.progress-bar{height:4px;background:var(--surface2);border-radius:4px;overflow:hidden;margin-top:10px;}
.table-wrap{overflow-x:auto;border-radius:var(--radius);border:1px solid var(--border);}
table{width:100%;border-collapse:collapse;}
th{padding:12px 16px;font-size:10px;text-transform:uppercase;letter-spacing:1.5px;color:var(--text3);text-align:left;background:var(--surface2);font-weight:600;border-bottom:1px solid var(--border);}
td{padding:14px 16px;font-size:13px;border-bottom:1px solid rgba(30,45,69,.5);font-family:'JetBrains Mono',monospace;color:var(--text2);}
tr:last-child td{border-bottom:none;}
tr:hover td{background:rgba(99,102,241,.03);}
.modal-overlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,.7);backdrop-filter:blur(4px);z-index:999;padding:20px;overflow-y:auto;align-items:center;justify-content:center;}
.modal-overlay.open{display:flex;}
.modal-box{background:var(--surface);border:1px solid var(--border2);border-radius:var(--radius);padding:28px;width:100%;max-width:860px;margin:auto;position:relative;animation:modalIn .2s ease;}
@keyframes modalIn{from{opacity:0;transform:scale(.96) translateY(10px);}to{opacity:1;transform:scale(1) translateY(0);}}
.modal-close{position:absolute;top:16px;right:16px;background:var(--surface2);border:1px solid var(--border);border-radius:6px;padding:4px 10px;color:var(--text3);cursor:pointer;font-size:13px;transition:all .15s;}
.modal-close:hover{color:var(--danger);border-color:var(--danger);}
.divider{height:1px;background:var(--border);margin:20px 0;}
.tag{display:inline-flex;align-items:center;gap:4px;padding:3px 10px;border-radius:20px;font-size:11px;font-weight:600;background:rgba(99,102,241,.1);color:var(--indigo-l);border:1px solid rgba(99,102,241,.2);}
.tag:hover{background:rgba(244,63,94,.1);color:var(--danger);border-color:rgba(244,63,94,.2);cursor:pointer;}
@keyframes fadeUp{from{opacity:0;transform:translateY(16px);}to{opacity:1;transform:translateY(0);}}
.fade-in{animation:fadeUp .4s ease both;}
.fade-in-1{animation-delay:.05s;}.fade-in-2{animation-delay:.1s;}.fade-in-3{animation-delay:.15s;}
::-webkit-scrollbar{width:6px;height:6px;}
::-webkit-scrollbar-track{background:transparent;}
::-webkit-scrollbar-thumb{background:var(--border2);border-radius:3px;}
@media(max-width:768px){
:root{--sidebar-w:0px;}
.sidebar{transform:translateX(-230px);}
.sidebar.open{transform:translateX(0);width:230px;}
.main{margin-left:0;}
.page-body{padding:20px 16px;}
.page-header{padding:20px 16px 16px;}
.stat-grid{grid-template-columns:1fr 1fr;}
.stock-grid{grid-template-columns:1fr;}
.mobile-toggle{display:flex!important;position:fixed;top:16px;left:16px;z-index:200;background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:8px 12px;cursor:pointer;color:var(--text);font-size:18px;align-items:center;}
}
.mobile-toggle{display:none;}
"""

CHART_JS = """
<script src="https://unpkg.com/lightweight-charts@4.1.3/dist/lightweight-charts.standalone.production.js"></script>
<script>
function buildChart(ticker) {
    document.getElementById('chartModalTitle').textContent = ticker;
    document.getElementById('chartContainer').innerHTML = '';
    document.getElementById('volumeContainer').innerHTML = '';
    document.getElementById('chartModal').classList.add('open');
    fetch('/chart?ticker='+ticker).then(r=>r.json()).then(data=>{
        const ce = document.getElementById('chartContainer');
        const ve = document.getElementById('volumeContainer');
        const chart = LightweightCharts.createChart(ce,{
            width:ce.clientWidth,height:380,
            layout:{background:{color:'transparent'},textColor:'#94a3b8'},
            grid:{vertLines:{color:'rgba(30,45,69,.5)'},horzLines:{color:'rgba(30,45,69,.5)'}},
            crosshair:{mode:LightweightCharts.CrosshairMode.Normal},
            rightPriceScale:{borderColor:'rgba(30,45,69,.8)'},
            timeScale:{borderColor:'rgba(30,45,69,.8)',timeVisible:true},
        });
        const cs=chart.addCandlestickSeries({upColor:'#34d399',downColor:'#f43f5e',borderUpColor:'#34d399',borderDownColor:'#f43f5e',wickUpColor:'#34d399',wickDownColor:'#f43f5e'});
        cs.setData(data.candles);
        chart.addLineSeries({color:'#22d3ee',lineWidth:1,title:'MA20'}).setData(data.ma20);
        chart.addLineSeries({color:'#f59e0b',lineWidth:1.5,title:'MA50'}).setData(data.ma50);
        chart.addLineSeries({color:'#8b5cf6',lineWidth:1.5,lineStyle:1,title:'MA200'}).setData(data.ma200);
        const vc=LightweightCharts.createChart(ve,{
            width:ve.clientWidth,height:100,
            layout:{background:{color:'transparent'},textColor:'#94a3b8'},
            grid:{vertLines:{color:'rgba(30,45,69,.3)'},horzLines:{visible:false}},
            rightPriceScale:{borderColor:'rgba(30,45,69,.8)'},
            timeScale:{borderColor:'rgba(30,45,69,.8)',visible:false},
        });
        const vs=vc.addHistogramSeries({priceFormat:{type:'volume'},priceScaleId:''});
        vs.priceScale().applyOptions({scaleMargins:{top:.1,bottom:0}});
        vs.setData(data.volumes);
        chart.timeScale().subscribeVisibleLogicalRangeChange(r=>vc.timeScale().setVisibleLogicalRange(r));
        chart.timeScale().fitContent();
    });
}
function closeChart(){
    document.getElementById('chartModal').classList.remove('open');
    document.getElementById('chartContainer').innerHTML='';
    document.getElementById('volumeContainer').innerHTML='';
}
</script>
"""

CHART_MODAL = """
<div class="modal-overlay" id="chartModal">
    <div class="modal-box" style="max-width:920px;">
        <button class="modal-close" onclick="closeChart()">✕ Close</button>
        <div id="chartModalTitle" style="font-size:20px;font-weight:800;margin-bottom:6px;letter-spacing:-.5px;"></div>
        <div style="font-size:12px;color:var(--text3);margin-bottom:20px;">Candlestick · MA20 · MA50 · MA200 · Volume</div>
        <div id="chartContainer" style="height:380px;border-radius:10px;overflow:hidden;background:var(--surface2);"></div>
        <div id="volumeContainer" style="height:100px;border-radius:10px;overflow:hidden;background:var(--surface2);margin-top:6px;"></div>
        <div style="display:flex;gap:16px;margin-top:12px;font-size:12px;color:var(--text3);">
            <span>&#9644; <span style="color:#22d3ee">MA20</span></span>
            <span>&#9644; <span style="color:#f59e0b">MA50</span></span>
            <span>&#9644; <span style="color:#8b5cf6">MA200</span></span>
            <span style="color:#34d399">&#9646; Bull</span>
            <span style="color:#f43f5e">&#9646; Bear</span>
        </div>
    </div>
</div>
"""

def sidebar(active):
    username = me()
    initials = username[0].upper() if username else "?"
    pages = [("home","🏠","Home","/"),("trading","🤖","Paper Trading","/trading"),
             ("registry","📊","Share Registry","/registry"),("alerts","🔔","Alerts","/alerts")]
    nav = "".join([f'<a href="{href}" class="nav-item {"active" if active==pid else ""}">'
                   f'<span class="nav-icon">{icon}</span>{label}</a>'
                   for pid,icon,label,href in pages])
    return f"""
<button class="mobile-toggle" onclick="document.getElementById('sb').classList.toggle('open')">☰</button>
<aside class="sidebar" id="sb">
    <div class="sidebar-logo">
        <div class="logo-mark">⚡</div>
        <div><div class="logo-text">VULCAN</div><div class="logo-sub">Trading Intelligence</div></div>
    </div>
    <nav class="sidebar-nav">
        <div class="nav-section">Navigation</div>{nav}
    </nav>
    <div class="sidebar-footer">
        <div class="user-card">
            <div class="user-avatar">{initials}</div>
            <div><div class="user-name">{username}</div><div class="user-role">Trader</div></div>
        </div>
        <a href="/logout" class="logout-link">↩ Sign out</a>
    </div>
</aside>"""


LOGIN_PAGE = """<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Vulcan — Sign In</title>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
{{CSS}}
body{display:flex;align-items:center;justify-content:center;min-height:100vh;position:relative;overflow:hidden;}
.orb{position:fixed;border-radius:50%;filter:blur(80px);opacity:.12;animation:float 8s ease-in-out infinite;}
.orb-1{width:500px;height:500px;background:var(--indigo);top:-150px;left:-150px;}
.orb-2{width:400px;height:400px;background:var(--vir);bottom:-100px;right:-100px;animation-delay:-3s;}
.orb-3{width:300px;height:300px;background:var(--violet);top:40%;left:50%;animation-delay:-6s;}
@keyframes float{0%,100%{transform:translate(0,0) scale(1);}33%{transform:translate(20px,-20px) scale(1.05);}66%{transform:translate(-10px,15px) scale(.97);}}
.bg-grid{position:fixed;inset:0;background-image:linear-gradient(rgba(99,102,241,.04) 1px,transparent 1px),linear-gradient(90deg,rgba(99,102,241,.04) 1px,transparent 1px);background-size:48px 48px;pointer-events:none;}
.wrap{width:100%;max-width:440px;padding:20px;position:relative;z-index:10;animation:fadeUp .5s ease both;}
@keyframes fadeUp{from{opacity:0;transform:translateY(24px);}to{opacity:1;transform:translateY(0);}}
.logo-mark-lg{width:64px;height:64px;background:linear-gradient(135deg,var(--indigo),var(--vir));border-radius:18px;display:flex;align-items:center;justify-content:center;font-size:28px;margin:0 auto 16px;box-shadow:0 0 40px rgba(99,102,241,.4),0 0 80px rgba(45,158,122,.2);animation:glow 3s ease-in-out infinite;}
@keyframes glow{0%,100%{box-shadow:0 0 30px rgba(99,102,241,.3),0 0 60px rgba(45,158,122,.15);}50%{box-shadow:0 0 50px rgba(99,102,241,.5),0 0 100px rgba(45,158,122,.25);}}
.lcard{background:rgba(13,18,32,.85);border:1px solid var(--border);border-radius:20px;padding:36px;backdrop-filter:blur(20px);position:relative;overflow:hidden;}
.lcard::before{content:'';position:absolute;top:0;left:10%;right:10%;height:1px;background:linear-gradient(90deg,transparent,rgba(99,102,241,.5),rgba(45,158,122,.3),transparent);}
.tabs{display:grid;grid-template-columns:1fr 1fr;gap:4px;background:var(--surface2);border-radius:10px;padding:4px;margin-bottom:28px;}
.tab{padding:10px;text-align:center;border-radius:7px;cursor:pointer;font-size:13px;font-weight:600;color:var(--text3);transition:all .2s;border:none;background:none;font-family:'Outfit',sans-serif;}
.tab.active{background:linear-gradient(135deg,rgba(99,102,241,.15),rgba(45,158,122,.1));color:var(--indigo-l);border:1px solid rgba(99,102,241,.25);}
.fg{margin-bottom:18px;}
.err{background:rgba(244,63,94,.08);border:1px solid rgba(244,63,94,.25);border-radius:10px;padding:12px 16px;font-size:13px;color:var(--danger);margin-bottom:18px;display:none;}
.err.show{display:block;animation:shake .3s ease;}
@keyframes shake{0%,100%{transform:translateX(0);}25%{transform:translateX(-5px);}75%{transform:translateX(5px);}}
.ok{background:rgba(52,211,153,.08);border:1px solid rgba(52,211,153,.25);border-radius:10px;padding:12px 16px;font-size:13px;color:var(--vir-l);margin-bottom:18px;display:none;}
.ok.show{display:block;}
.lbtn{width:100%;padding:14px;background:linear-gradient(135deg,var(--indigo),var(--violet));color:white;border:none;border-radius:10px;font-size:15px;font-weight:700;font-family:'Outfit',sans-serif;cursor:pointer;margin-top:8px;transition:all .2s;box-shadow:0 4px 20px rgba(99,102,241,.3);}
.lbtn:hover{transform:translateY(-1px);box-shadow:0 8px 28px rgba(99,102,241,.4);}
.lbtn:disabled{opacity:.5;transform:none;cursor:not-allowed;}
</style></head>
<body>
<div class="orb orb-1"></div><div class="orb orb-2"></div><div class="orb orb-3"></div>
<div class="bg-grid"></div>
<div class="wrap">
    <div style="text-align:center;margin-bottom:36px;">
        <div class="logo-mark-lg">⚡</div>
        <h1 style="font-size:36px;font-weight:800;letter-spacing:-1px;background:linear-gradient(135deg,var(--indigo-l),var(--vir-l));-webkit-background-clip:text;-webkit-text-fill-color:transparent;">VULCAN</h1>
        <p style="font-size:12px;color:var(--text3);letter-spacing:3px;text-transform:uppercase;margin-top:4px;">Trading Intelligence</p>
    </div>
    <div class="lcard">
        <div class="tabs">
            <button class="tab active" onclick="switchTab('login')">Sign In</button>
            <button class="tab" onclick="switchTab('register')">Register</button>
        </div>
        <div id="errBox" class="err"></div>
        <div id="okBox" class="ok"></div>
        <form id="loginForm" onsubmit="doLogin(event)">
            <div class="fg"><label class="form-label">Username</label><input type="text" id="lu" class="input" placeholder="your_username" required></div>
            <div class="fg"><label class="form-label">Password</label><input type="password" id="lp" class="input" placeholder="••••••••" required></div>
            <button type="submit" class="lbtn" id="lbtn">Access Dashboard →</button>
        </form>
        <form id="regForm" onsubmit="doReg(event)" style="display:none;">
            <div class="fg"><label class="form-label">Username</label><input type="text" id="ru" class="input" placeholder="choose_a_username" required></div>
            <div class="fg"><label class="form-label">Password</label><input type="password" id="rp" class="input" placeholder="min. 6 characters" required></div>
            <div class="fg"><label class="form-label">Confirm Password</label><input type="password" id="rc" class="input" placeholder="repeat password" required></div>
            <button type="submit" class="lbtn" id="rbtn">Create Account →</button>
        </form>
        <div style="text-align:center;margin-top:20px;font-size:11px;color:var(--text3);line-height:1.7;">Paper trading · ML signals · Community registry</div>
    </div>
</div>
<script>
function switchTab(t){
    ['login','register'].forEach((x,i)=>{
        document.querySelectorAll('.tab')[i].classList.toggle('active',x===t);
        document.getElementById(x==='login'?'loginForm':'regForm').style.display=x===t?'block':'none';
    });
    clearMsgs();
}
function showErr(m){const e=document.getElementById('errBox');e.textContent='⚠ '+m;e.className='err show';document.getElementById('okBox').className='ok';}
function showOk(m){const e=document.getElementById('okBox');e.textContent='✓ '+m;e.className='ok show';document.getElementById('errBox').className='err';}
function clearMsgs(){document.getElementById('errBox').className='err';document.getElementById('okBox').className='ok';}
async function doLogin(e){
    e.preventDefault();
    const btn=document.getElementById('lbtn');btn.disabled=true;btn.textContent='Authenticating...';clearMsgs();
    const r=await fetch('/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:document.getElementById('lu').value.trim(),password:document.getElementById('lp').value})});
    const d=await r.json();
    if(d.success){btn.textContent='✓ Redirecting...';window.location.href='/';}
    else{showErr(d.error);btn.disabled=false;btn.textContent='Access Dashboard →';}
}
async function doReg(e){
    e.preventDefault();
    const p=document.getElementById('rp').value,c=document.getElementById('rc').value;
    clearMsgs();
    if(p!==c){showErr("Passwords don't match.");return;}
    if(p.length<6){showErr("Password must be at least 6 characters.");return;}
    const btn=document.getElementById('rbtn');btn.disabled=true;btn.textContent='Creating...';
    const r=await fetch('/auth/register',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:document.getElementById('ru').value.trim(),password:p})});
    const d=await r.json();
    if(d.success){showOk('Account created! Sign in now.');setTimeout(()=>switchTab('login'),1500);}
    else showErr(d.error);
    btn.disabled=false;btn.textContent='Create Account →';
}
</script>
</body></html>"""


@app.route("/login")
def login():
    if logged_in(): return redirect(url_for("home"))
    return LOGIN_PAGE.replace("{CSS}", CSS)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/auth/login", methods=["POST"])
def auth_login():
    data = request.json
    username = data.get("username","").strip().lower()
    password = data.get("password","")
    if not username or not password:
        return jsonify({"success":False,"error":"Username and password required."})
    users = load_users()
    if username not in users or users[username]["password"] != hash_pw(password):
        return jsonify({"success":False,"error":"Invalid username or password."})
    session["username"] = username
    session.permanent = True
    return jsonify({"success":True})

@app.route("/auth/register", methods=["POST"])
def auth_register():
    data = request.json
    username = data.get("username","").strip().lower()
    password = data.get("password","")
    if not username or not password: return jsonify({"success":False,"error":"All fields required."})
    if len(username)<3: return jsonify({"success":False,"error":"Username: min 3 characters."})
    if not username.replace("_","").replace("-","").isalnum(): return jsonify({"success":False,"error":"Letters, numbers, - and _ only."})
    users = load_users()
    if username in users: return jsonify({"success":False,"error":"Username already taken."})
    users[username] = {"password":hash_pw(password),"created":datetime.now().isoformat()}
    save_users(users)
    return jsonify({"success":True})

@app.route("/")
def home():
    if not logged_in(): return redirect(url_for("login"))
    watchlist = load_watchlist()
    stocks = [d for t in watchlist for d in [analyze_stock(t)] if d]
    market = []
    for t,n in [("SPY","S&P 500"),("QQQ","Nasdaq"),("DIA","Dow Jones")]:
        try:
            d = yf.Ticker(t).history(period="2d")
            if len(d)>=2:
                p,pr = round(d["Close"].iloc[-1],2), round(d["Close"].iloc[-2],2)
                market.append({"name":n,"price":p,"change":round(((p-pr)/pr)*100,2)})
        except: pass

    mkt_html = "".join([f'<div class="market-item"><div><div class="market-name">{m["name"]}</div>'
        f'<div class="market-price">${m["price"]}</div></div>'
        f'<span class="{"up" if m["change"]>=0 else "down"}" style="font-size:12px;font-family:\'JetBrains Mono\',monospace;">{"▲" if m["change"]>=0 else "▼"} {abs(m["change"])}%</span></div>'
        for m in market])

    cards = ""
    for s in stocks:
        bull = s["prediction"]==1
        proba_pct = int(s.get("proba",0.5)*100)
        chg = s.get("change_pct",0)
        chg_color = "up" if chg>=0 else "down"
        cards += f"""<div class="stock-card {"bull" if bull else "bear"}" onclick="buildChart('{s["ticker"]}')">
            <div class="stock-header">
                <div><div class="stock-ticker">{s["ticker"]}</div></div>
                <div style="display:flex;flex-direction:column;align-items:flex-end;gap:5px;">
                    <span class="badge {"badge-bull" if bull else "badge-bear"}">{"↑ BUY" if bull else "↓ SELL"}</span>
                    <span class="badge {"badge-high" if s["confidence"]=="High" else "badge-warn"}">{s["confidence"]}</span>
                </div>
            </div>
            <div class="stock-price">${s["price"]}</div>
            <div class="stock-change {chg_color}">{("+" if chg>=0 else "")}{chg}% today</div>
            <div class="stock-stats">
                <div class="mini-stat"><div class="mini-label">RSI</div><div class="mini-value {"down" if s["rsi"]>70 else "up" if s["rsi"]<30 else ""}">{s["rsi"]}</div></div>
                <div class="mini-stat"><div class="mini-label">MA50</div><div class="mini-value">{s["ma50"]}</div></div>
                <div class="mini-stat"><div class="mini-label">MA200</div><div class="mini-value">{s["ma200"]}</div></div>
                <div class="mini-stat"><div class="mini-label">Signal %</div><div class="mini-value {"up" if bull else "down"}">{proba_pct}%</div></div>
            </div>
            <div class="progress-bar"><div style="height:100%;border-radius:4px;width:{proba_pct}%;background:linear-gradient(90deg,{"var(--vir)" if bull else "var(--danger)"},{"var(--indigo-l)" if bull else "var(--violet)"});"></div></div>
        </div>"""

    wl_tags = "".join([f'<span class="tag" onclick="removeStock(\'{t}\')">{t} ×</span>' for t in watchlist])

    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Vulcan — Home</title>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>{CSS}</style></head>
<body>{sidebar("home")}
<div class="main">
<div class="market-bar">{mkt_html}</div>
<div class="page-header">
    <div class="page-title">Market Overview</div>
    <div class="page-subtitle">Watchlist signals · Stock search · AI recommendations</div>
</div>
<div class="page-body">
    <div class="card fade-in" style="margin-bottom:24px;">
        <div class="card-title">🔍 Stock Search</div>
        <div style="display:flex;gap:10px;">
            <input type="text" id="si" class="input" placeholder="Search any ticker (e.g. TSLA) and press Enter" style="flex:1;">
            <button class="btn btn-primary" onclick="doSearch()">Analyze</button>
        </div>
        <div id="sr" style="margin-top:16px;"></div>
    </div>
    <div class="card fade-in fade-in-1" style="margin-bottom:24px;">
        <div class="card-title">📋 Watchlist</div>
        <div style="display:flex;gap:10px;margin-bottom:14px;">
            <input type="text" id="ai" class="input" placeholder="Add ticker..." style="max-width:200px;">
            <button class="btn btn-green" onclick="addStock()">+ Add</button>
        </div>
        <div style="display:flex;flex-wrap:wrap;gap:8px;">{wl_tags}</div>
    </div>
    <div style="margin-bottom:24px;" class="fade-in fade-in-2">
        <button class="btn btn-outline btn-block" onclick="getRecs()" id="recBtn" style="padding:14px;">⚡ Get AI Recommendations</button>
        <div id="recResult" style="margin-top:16px;"></div>
    </div>
    <div class="card-title fade-in fade-in-2" style="margin-bottom:16px;">Watchlist Signals</div>
    <div class="stock-grid fade-in fade-in-3">{cards}</div>
</div></div>
{CHART_MODAL}
{CHART_JS}
<script>
document.getElementById('si').addEventListener('keydown',e=>{{if(e.key==='Enter')doSearch();}});
function doSearch(){{
    const t=document.getElementById('si').value.trim().toUpperCase();if(!t)return;
    const el=document.getElementById('sr');
    el.innerHTML='<div style="color:var(--text3);font-size:13px;">Analyzing '+t+'...</div>';
    fetch('/search?ticker='+t).then(r=>r.json()).then(d=>{{
        if(d.error){{el.innerHTML='<div style="color:var(--danger)">Could not find '+t+'</div>';return;}}
        const bull=d.prediction===1,p=Math.round((d.proba||.5)*100);
        el.innerHTML=`<div style="background:var(--surface2);border:1px solid var(--border);border-radius:12px;padding:20px;display:flex;flex-wrap:wrap;gap:20px;align-items:center;justify-content:space-between;">
            <div><div style="font-size:22px;font-weight:800;cursor:pointer;" onclick="buildChart('${{d.ticker}}')">${{d.ticker}} <span style="font-size:13px;color:var(--text3);">→ chart</span></div>
            <div style="font-size:28px;font-weight:800;font-family:'JetBrains Mono',monospace;margin-top:4px;">$$${{d.price}}</div></div>
            <div style="display:flex;flex-direction:column;gap:8px;align-items:flex-end;">
                <span class="badge ${{bull?'badge-bull':'badge-bear'}}">${{bull?'↑ BUY':'↓ SELL'}}</span>
                <span class="badge badge-high">Confidence: ${{d.confidence}}</span>
                <span style="font-size:12px;color:var(--text3);">Signal: ${{p}}%</span>
            </div>
            <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;">
                <div class="mini-stat"><div class="mini-label">RSI</div><div class="mini-value">${{d.rsi}}</div></div>
                <div class="mini-stat"><div class="mini-label">MA50</div><div class="mini-value">${{d.ma50}}</div></div>
                <div class="mini-stat"><div class="mini-label">MA200</div><div class="mini-value">${{d.ma200}}</div></div>
            </div></div>`;
    }});
}}
function addStock(){{const t=document.getElementById('ai').value.trim().toUpperCase();if(!t)return;fetch('/add_stock',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{ticker:t}})}}).then(()=>location.reload());}}
function removeStock(t){{fetch('/remove_stock',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{ticker:t}})}}).then(()=>location.reload());}}
function getRecs(){{
    const btn=document.getElementById('recBtn'),div=document.getElementById('recResult');
    btn.disabled=true;btn.textContent='⏳ Scanning market...';div.innerHTML='';
    fetch('/recommend').then(r=>r.json()).then(data=>{{
        btn.disabled=false;btn.textContent='⚡ Get AI Recommendations';
        let h='<div class="card"><div class="card-title">⚡ AI Recommendations</div>';
        if(data.buys.length){{
            h+='<div style="font-size:13px;font-weight:700;color:var(--vir-l);margin-bottom:10px;">Strong Buys</div>';
            data.buys.forEach(s=>{{h+=`<div style="display:flex;justify-content:space-between;align-items:center;padding:10px;background:var(--surface2);border-radius:8px;margin-bottom:6px;cursor:pointer;" onclick="buildChart('${{s.ticker}}')">`+
                `<span style="font-weight:700;">${{s.ticker}}</span><span style="color:var(--text3);font-size:12px;font-family:'JetBrains Mono',monospace;">$$${{s.price}}</span>`+
                `<span style="color:var(--text3);font-size:12px;">RSI ${{s.rsi}}</span><span class="badge badge-bull">↑ ${{s.confidence}}</span></div>`;}});
        }}
        if(data.sells.length){{
            h+='<div style="font-size:13px;font-weight:700;color:var(--danger);margin:14px 0 10px;">Strong Sells</div>';
            data.sells.forEach(s=>{{h+=`<div style="display:flex;justify-content:space-between;align-items:center;padding:10px;background:var(--surface2);border-radius:8px;margin-bottom:6px;cursor:pointer;" onclick="buildChart('${{s.ticker}}')">`+
                `<span style="font-weight:700;">${{s.ticker}}</span><span style="color:var(--text3);font-size:12px;font-family:'JetBrains Mono',monospace;">$$${{s.price}}</span>`+
                `<span style="color:var(--text3);font-size:12px;">RSI ${{s.rsi}}</span><span class="badge badge-bear">↓ ${{s.confidence}}</span></div>`;}});
        }}
        h+='</div>';div.innerHTML=h;
    }}).catch(()=>{{btn.disabled=false;btn.textContent='⚡ Get AI Recommendations';}});
}}
</script></body></html>"""
    return html


@app.route("/trading")
def trading():
    if not logged_in(): return redirect(url_for("login"))
    portfolio = load_portfolio(me())
    starting = portfolio.get("starting_cash",10000)
    cash = portfolio.get("cash",starting)
    positions = portfolio.get("positions",{})
    trades = portfolio.get("trades",[])
    total_pos_val = 0
    pos_rows = ""
    for ticker, pos in positions.items():
        if pos["shares"]>0:
            try:
                cur = round(yf.Ticker(ticker).history(period="1d")["Close"].iloc[-1],2)
                val = round(pos["shares"]*cur,2)
                pnl = round((cur-pos["buy_price"])*pos["shares"],2)
                pnl_pct = round(((cur-pos["buy_price"])/pos["buy_price"])*100,2)
                total_pos_val += val
                pc = "up" if pnl>=0 else "down"
                pos_rows += f"<tr><td style='color:var(--text);font-weight:700;cursor:pointer;' onclick=\"buildChart('{ticker}')\">{ticker}</td><td>{pos['shares']}</td><td>${pos['buy_price']}</td><td>${cur}</td><td>${val}</td><td class='{pc}'>{'+' if pnl>=0 else ''}${pnl} ({'+' if pnl_pct>=0 else ''}{pnl_pct}%)</td></tr>"
            except: pass
    if not pos_rows: pos_rows="<tr><td colspan='6' style='color:var(--text3);text-align:center;padding:30px;'>No open positions</td></tr>"
    total = round(cash+total_pos_val,2)
    ret = round(((total-starting)/starting)*100,2)
    rc = "up" if ret>=0 else "down"
    trade_rows = ""
    for t in reversed(trades[-50:]):
        if isinstance(t,dict):
            ac = "up" if t.get("action")=="BUY" else "down"
            profit_cell = f"<td class='up'>+${t.get('profit','')}</td>" if t.get("action")=="SELL" else "<td>—</td>"
            conf = t.get("confidence","")
            badge_cls = "badge-high" if conf=="High" else "badge-warn"
            trade_rows += f"<tr><td class='{ac}' style='font-weight:700;'>{t.get('action','')}</td><td style='color:var(--text);font-weight:700;'>{t.get('ticker','')}</td><td>${t.get('price','')}</td><td>{t.get('shares','')}</td><td>${t.get('total','')}</td>{profit_cell}<td style='color:var(--text3);font-size:11px;'>{t.get('date','')}</td><td><span class='badge {badge_cls}'>{conf}</span></td></tr>"
        else:
            trade_rows += f"<tr><td colspan='8' style='color:var(--text3);'>{t}</td></tr>"
    if not trade_rows: trade_rows="<tr><td colspan='8' style='color:var(--text3);text-align:center;padding:30px;'>No trades yet — run the bot</td></tr>"
    open_count = len([p for p in positions.values() if p["shares"]>0])
    cash_pct = round((cash/total)*100,1) if total>0 else 100

    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Vulcan — Paper Trading</title>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>{CSS}</style></head>
<body>{sidebar("trading")}
<div class="main">
<div class="page-header">
    <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px;">
        <div><div class="page-title">Paper Trading</div><div class="page-subtitle">AI-driven autonomous trading · {me()}'s portfolio</div></div>
        <div style="display:flex;gap:10px;">
            <button class="btn btn-green" onclick="runBot()" id="runBtn">▶ Run Bot</button>
            <button class="btn btn-outline" onclick="document.getElementById('cashModal').classList.add('open')">💰 Set Cash</button>
        </div>
    </div>
</div>
<div class="page-body">
    <div class="stat-grid fade-in">
        <div class="stat-card"><div class="stat-label">Portfolio Value</div><div class="stat-value {rc}">${total:,.2f}</div><div class="stat-sub">Starting: ${starting:,.2f}</div></div>
        <div class="stat-card"><div class="stat-label">Cash Available</div><div class="stat-value neutral">${cash:,.2f}</div><div class="stat-sub">{cash_pct}% of portfolio</div></div>
        <div class="stat-card"><div class="stat-label">Total Return</div><div class="stat-value {rc}">{('+' if ret>=0 else '')}{ret}%</div><div class="stat-sub">P&amp;L: ${round(total-starting,2):+,.2f}</div></div>
        <div class="stat-card"><div class="stat-label">Open Positions</div><div class="stat-value neutral">{open_count}</div><div class="stat-sub">Total trades: {len(trades)}</div></div>
    </div>
    <div class="card fade-in fade-in-1" style="margin-bottom:24px;">
        <div class="card-title">Open Positions</div>
        <div class="table-wrap"><table><thead><tr><th>Ticker</th><th>Shares</th><th>Avg Cost</th><th>Current</th><th>Value</th><th>P&amp;L</th></tr></thead><tbody>{pos_rows}</tbody></table></div>
    </div>
    <div class="card fade-in fade-in-2">
        <div class="card-title">Trade History</div>
        <div class="table-wrap"><table><thead><tr><th>Action</th><th>Ticker</th><th>Price</th><th>Shares</th><th>Total</th><th>Profit</th><th>Date</th><th>Confidence</th></tr></thead><tbody>{trade_rows}</tbody></table></div>
    </div>
</div></div>
<div class="modal-overlay" id="cashModal">
    <div class="modal-box" style="max-width:400px;">
        <button class="modal-close" onclick="document.getElementById('cashModal').classList.remove('open')">✕</button>
        <div style="font-size:20px;font-weight:800;margin-bottom:6px;">Set Starting Cash</div>
        <div style="font-size:13px;color:var(--text3);margin-bottom:24px;">Resets your paper account — all positions and trades cleared.</div>
        <label class="form-label">Amount ($)</label>
        <input type="number" id="cashAmt" class="input" value="{starting}" min="100" style="margin-bottom:16px;">
        <button class="btn btn-primary btn-block" onclick="setCash()">Reset with New Cash</button>
    </div>
</div>
{CHART_MODAL}{CHART_JS}
<script>
function runBot(){{const btn=document.getElementById('runBtn');btn.disabled=true;btn.textContent='⏳ Running...';fetch('/run').then(r=>r.json()).then(()=>{{btn.textContent='✓ Done!';setTimeout(()=>location.reload(),1000);}}).catch(()=>{{btn.disabled=false;btn.textContent='▶ Run Bot';}});}}
function setCash(){{const a=parseFloat(document.getElementById('cashAmt').value);if(!a||a<100)return;fetch('/set_cash',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{amount:a}})}}).then(()=>location.reload());}}
</script></body></html>"""
    return html


@app.route("/registry")
def registry():
    if not logged_in(): return redirect(url_for("login"))
    reg_data = get_registry_with_flags()
    holdings = load_holdings()
    flagged_count = sum(1 for r in reg_data if r["flagged"])
    total_holders = sum(r["holders"] for r in reg_data)

    reg_rows = ""
    for r in reg_data:
        float_str = f"{r['float_shares']:,}" if r["float_shares"] else "N/A"
        flag_html = f'<span class="badge badge-warn">⚠ {r["flag_reason"]}</span>' if r["flagged"] else '<span class="badge" style="background:rgba(52,211,153,.1);color:var(--vir-l);border-color:rgba(52,211,153,.2);">✓ Clean</span>'
        reg_rows += f"<tr><td style='color:var(--text);font-weight:700;'>{r['ticker']}</td><td>{r['community_shares']:,}</td><td style='color:var(--text3);'>{float_str}</td><td>{r['holders']}</td><td>{flag_html}</td></tr>"
    if not reg_rows: reg_rows="<tr><td colspan='5' style='color:var(--text3);text-align:center;padding:40px;'>No holdings registered yet.</td></tr>"

    hold_rows = ""
    for i,h in enumerate(holdings):
        hold_rows += f"<tr><td style='color:var(--text);font-weight:700;'>{h['ticker']}</td><td>{h['shares']}</td><td>${h['buy_price']}</td><td><button class='btn btn-danger' style='padding:4px 10px;font-size:11px;' onclick='removeHolding({i})'>Remove</button></td></tr>"
    if not hold_rows: hold_rows="<tr><td colspan='4' style='color:var(--text3);text-align:center;padding:20px;'>No holdings added</td></tr>"

    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Vulcan — Registry</title>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>{CSS}</style></head>
<body>{sidebar("registry")}
<div class="main">
<div class="page-header">
    <div class="page-title">Public Share Registry</div>
    <div class="page-subtitle">Community holdings · Cross-referenced against real float data · Fraud detection</div>
</div>
<div class="page-body">
    <div class="stat-grid fade-in">
        <div class="stat-card"><div class="stat-label">Tracked Tickers</div><div class="stat-value neutral">{len(reg_data)}</div></div>
        <div class="stat-card"><div class="stat-label">Flagged</div><div class="stat-value {"down" if flagged_count>0 else "up"}">{flagged_count}</div><div class="stat-sub">Suspicious entries</div></div>
        <div class="stat-card"><div class="stat-label">Total Holders</div><div class="stat-value neutral">{total_holders}</div></div>
    </div>
    <div class="card fade-in fade-in-1" style="margin-bottom:24px;">
        <div class="card-title">📝 Register Your Holdings</div>
        <p style="color:var(--text3);font-size:13px;margin-bottom:16px;">Add your real stock positions to the community registry. Only share counts are public.</p>
        <div style="display:grid;grid-template-columns:1fr 1fr 1fr auto;gap:10px;flex-wrap:wrap;">
            <div><label class="form-label">Ticker</label><input type="text" id="ht" class="input" placeholder="AAPL"></div>
            <div><label class="form-label">Shares</label><input type="number" id="hs" class="input" placeholder="10"></div>
            <div><label class="form-label">Avg Buy Price</label><input type="number" id="hp" class="input" placeholder="150.00"></div>
            <div style="display:flex;align-items:flex-end;"><button class="btn btn-green" onclick="addHolding()">+ Register</button></div>
        </div>
    </div>
    <div class="card fade-in fade-in-2" style="margin-bottom:24px;">
        <div class="card-title">My Registered Holdings</div>
        <div class="table-wrap"><table><thead><tr><th>Ticker</th><th>Shares</th><th>Buy Price</th><th>Action</th></tr></thead><tbody>{hold_rows}</tbody></table></div>
    </div>
    <div class="card fade-in fade-in-3">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
            <div class="card-title" style="margin-bottom:0;">Community Registry</div>
            <button class="btn btn-outline" onclick="location.reload()" style="font-size:12px;padding:6px 12px;">↻ Refresh</button>
        </div>
        <div class="table-wrap"><table><thead><tr><th>Ticker</th><th>Community Shares</th><th>Real Float</th><th>Holders</th><th>Status</th></tr></thead><tbody>{reg_rows}</tbody></table></div>
        <div style="margin-top:16px;padding:14px;background:var(--surface2);border-radius:10px;font-size:12px;color:var(--text3);line-height:1.7;">
            ⚠ <strong style="color:var(--text2);">Fraud detection:</strong> Community holdings are cross-referenced against real public float data from Yahoo Finance. Entries are flagged when community claims exceed an unusual percentage of a stock's float, or when identical share counts suggest copy-paste fraud.
        </div>
    </div>
</div></div>
<script>
function addHolding(){{
    const t=document.getElementById('ht').value.trim().toUpperCase(),s=parseFloat(document.getElementById('hs').value),p=parseFloat(document.getElementById('hp').value);
    if(!t||!s||!p){{alert('Fill all fields.');return;}}
    fetch('/add_holding',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{ticker:t,shares:s,buy_price:p}})}}).then(()=>location.reload());
}}
function removeHolding(i){{fetch('/remove_holding',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{index:i}})}}).then(()=>location.reload());}}
</script></body></html>"""
    return html

@app.route("/alerts")
def alerts_view():
    if not logged_in(): return redirect(url_for("login"))
    triggered = check_alerts()
    settings = load_settings()
    for alert in triggered: send_alert_email(alert, settings)
    alerts = load_alerts()
    alert_rows = ""
    for i,a in enumerate(alerts):
        dc = "up" if a["direction"]=="above" else "down"
        alert_rows += f"<tr><td style='color:var(--text);font-weight:700;'>{a['ticker']}</td><td class='{dc}'>{a['direction'].capitalize()}</td><td style='font-family:\"JetBrains Mono\",monospace;'>${a['target']}</td><td><span class='badge badge-warn'>Active</span></td><td><button class='btn btn-danger' style='padding:4px 10px;font-size:11px;' onclick='removeAlert({i})'>Remove</button></td></tr>"
    if not alert_rows: alert_rows="<tr><td colspan='5' style='color:var(--text3);text-align:center;padding:30px;'>No active alerts</td></tr>"
    triggered_banner = "".join([f'<div style="background:rgba(52,211,153,.08);border:1px solid rgba(52,211,153,.25);border-radius:10px;padding:12px 16px;font-size:13px;color:var(--vir-l);margin-bottom:12px;">🔔 {a["ticker"]} hit ${a["current_price"]} (target: ${a["target"]} {a["direction"]})</div>' for a in triggered])

    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Vulcan — Alerts</title>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>{CSS}</style></head>
<body>{sidebar("alerts")}
<div class="main">
<div class="page-header">
    <div class="page-title">Price Alerts</div>
    <div class="page-subtitle">Get notified when stocks hit your target price</div>
</div>
<div class="page-body">
    {triggered_banner}
    <div class="card fade-in" style="margin-bottom:24px;">
        <div class="card-title">+ New Alert</div>
        <div style="display:grid;grid-template-columns:1fr 1fr 1fr auto;gap:10px;">
            <div><label class="form-label">Ticker</label><input type="text" id="at" class="input" placeholder="AAPL"></div>
            <div><label class="form-label">Target Price</label><input type="number" id="ap" class="input" placeholder="200.00"></div>
            <div><label class="form-label">Condition</label><select id="ad" class="input"><option value="above">Rises above</option><option value="below">Falls below</option></select></div>
            <div style="display:flex;align-items:flex-end;"><button class="btn btn-primary" onclick="addAlert()">+ Add</button></div>
        </div>
    </div>
    <div class="card fade-in fade-in-1" style="margin-bottom:24px;">
        <div class="card-title">Active Alerts</div>
        <div class="table-wrap"><table><thead><tr><th>Ticker</th><th>Direction</th><th>Target</th><th>Status</th><th>Action</th></tr></thead><tbody>{alert_rows}</tbody></table></div>
    </div>
    <div class="card fade-in fade-in-2">
        <div class="card-title">📧 Email Notifications</div>
        <p style="color:var(--text3);font-size:13px;margin-bottom:20px;line-height:1.7;">Connect Gmail to receive notifications when alerts trigger. Use a Gmail App Password — generate at <span style="color:var(--indigo-l);">myaccount.google.com → Security → App Passwords</span>.</p>
        <div style="display:grid;grid-template-columns:1fr 1fr 1fr auto;gap:10px;">
            <div><label class="form-label">Your Email</label><input type="email" id="se" class="input" value="{settings.get('email','')}"></div>
            <div><label class="form-label">Gmail Sender</label><input type="email" id="sg" class="input" value="{settings.get('gmail_user','')}"></div>
            <div><label class="form-label">App Password</label><input type="password" id="sp" class="input" placeholder="16-char code"></div>
            <div style="display:flex;align-items:flex-end;"><button class="btn btn-outline" onclick="saveSettings()">Save</button></div>
        </div>
    </div>
</div></div>
<script>
function addAlert(){{const t=document.getElementById('at').value.trim().toUpperCase(),p=parseFloat(document.getElementById('ap').value),d=document.getElementById('ad').value;if(!t||!p)return;fetch('/add_alert',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{ticker:t,target:p,direction:d}})}}).then(()=>location.reload());}}
function removeAlert(i){{fetch('/remove_alert',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{index:i}})}}).then(()=>location.reload());}}
function saveSettings(){{fetch('/save_settings',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{email:document.getElementById('se').value,gmail_user:document.getElementById('sg').value,gmail_pass:document.getElementById('sp').value}})}}).then(()=>alert('Settings saved!'));}}
</script></body></html>"""
    return html

@app.route("/run")
def run():
    if not logged_in(): return jsonify({"error":"Unauthorized"}),401
    run_bot(me())
    return jsonify({"status":"done"})

@app.route("/set_cash", methods=["POST"])
def set_cash():
    if not logged_in(): return jsonify({"error":"Unauthorized"}),401
    set_starting_cash(me(), float(request.json.get("amount",10000)))
    return jsonify({"status":"done"})

@app.route("/search")
def search():
    if not logged_in(): return jsonify({"error":"Unauthorized"}),401
    ticker = request.args.get("ticker","").upper()
    if not ticker: return jsonify({"error":"No ticker"})
    data = analyze_stock(ticker)
    return jsonify(data) if data else jsonify({"error":"Stock not found"})

@app.route("/recommend")
def recommend():
    if not logged_in(): return jsonify({"error":"Unauthorized"}),401
    SCAN = ["AAPL","MSFT","GOOGL","AMZN","TSLA","NVDA","META","SPY","QQQ","AMD","NFLX","DIS","BRK-B","JPM","BAC"]
    buys,sells = [],[]
    for t in SCAN:
        d = analyze_stock(t)
        if d and d["confidence"]=="High":
            (buys if d["prediction"]==1 else sells).append(d)
    return jsonify({"buys":sorted(buys,key=lambda x:x["rsi"]),"sells":sorted(sells,key=lambda x:x["rsi"],reverse=True)})

@app.route("/chart")
def chart():
    if not logged_in(): return jsonify({"error":"Unauthorized"}),401
    ticker = request.args.get("ticker","").upper()
    if not ticker: return jsonify({"error":"No ticker"})
    return jsonify(get_chart_data(ticker))

@app.route("/add_stock",methods=["POST"])
def add_stock():
    if not logged_in(): return jsonify({"error":"Unauthorized"}),401
    ticker = request.json.get("ticker","").upper()
    wl = load_watchlist()
    if ticker and ticker not in wl: wl.append(ticker); save_watchlist(wl)
    return jsonify({"status":"added"})

@app.route("/remove_stock",methods=["POST"])
def remove_stock():
    if not logged_in(): return jsonify({"error":"Unauthorized"}),401
    ticker = request.json.get("ticker","").upper()
    wl = load_watchlist()
    if ticker in wl: wl.remove(ticker); save_watchlist(wl)
    return jsonify({"status":"removed"})

@app.route("/add_alert",methods=["POST"])
def add_alert():
    if not logged_in(): return jsonify({"error":"Unauthorized"}),401
    d = request.json
    alerts = load_alerts()
    alerts.append({"ticker":d.get("ticker","").upper(),"target":float(d.get("target",0)),"direction":d.get("direction","above")})
    save_alerts(alerts)
    return jsonify({"status":"added"})

@app.route("/remove_alert",methods=["POST"])
def remove_alert():
    if not logged_in(): return jsonify({"error":"Unauthorized"}),401
    i = request.json.get("index",-1)
    alerts = load_alerts()
    if 0<=i<len(alerts): alerts.pop(i); save_alerts(alerts)
    return jsonify({"status":"removed"})

@app.route("/save_settings",methods=["POST"])
def save_settings_route():
    if not logged_in(): return jsonify({"error":"Unauthorized"}),401
    from trader import SETTINGS_FILE
    with open(SETTINGS_FILE,"w") as f: json.dump(request.json,f)
    return jsonify({"status":"saved"})

@app.route("/add_holding",methods=["POST"])
def add_holding():
    if not logged_in(): return jsonify({"error":"Unauthorized"}),401
    d = request.json
    ticker = d.get("ticker","").upper()
    shares = float(d.get("shares",0))
    buy_price = float(d.get("buy_price",0))
    if not ticker or not shares or not buy_price: return jsonify({"error":"Missing data"})
    holdings = load_holdings()
    holdings.append({"ticker":ticker,"shares":shares,"buy_price":buy_price})
    with open(HOLDINGS_FILE,"w") as f: json.dump(holdings,f)
    update_registry(me(),ticker,shares,buy_price,"add")
    return jsonify({"status":"added"})

@app.route("/remove_holding",methods=["POST"])
def remove_holding():
    if not logged_in(): return jsonify({"error":"Unauthorized"}),401
    i = request.json.get("index",-1)
    holdings = load_holdings()
    if 0<=i<len(holdings):
        ticker = holdings[i]["ticker"]
        holdings.pop(i)
        with open(HOLDINGS_FILE,"w") as f: json.dump(holdings,f)
        update_registry(me(),ticker,0,0,"remove")
    return jsonify({"status":"removed"})

if __name__=="__main__":
    app.run(debug=True,host="0.0.0.0")