from flask import Flask,render_template_string,jsonify,request,session,redirect,url_for
import yfinance as yf
import json,os,hashlib,secrets
from datetime import datetime
from trader import (analyze_stock,run_bot,get_chart_data,load_watchlist,save_watchlist,
    load_alerts,save_alerts,check_alerts,send_alert_email,load_settings,save_settings,
    load_portfolio,save_portfolio,set_starting_cash,
    load_registry,get_registry_with_flags,update_registry,ensure_dirs,STRATEGIES)

app=Flask(__name__)
app.secret_key=secrets.token_hex(32)
USERS_FILE="users.json"
HOLDINGS_FILE="holdings.json"
ensure_dirs()

def hash_pw(pw): return hashlib.sha256(pw.encode()).hexdigest()
def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE,encoding="utf-8") as f: return json.load(f)
    return {}
def save_users(u):
    with open(USERS_FILE,"w",encoding="utf-8") as f: json.dump(u,f)
def logged_in(): return "username" in session
def me(): return session.get("username","")
def load_holdings():
    if os.path.exists(HOLDINGS_FILE):
        with open(HOLDINGS_FILE,encoding="utf-8") as f: return json.load(f)
    return []


# ── MARKET TICKERS shown in top bar ──────────────────────────────────────────
MARKET_TICKERS = [
    ("SPY","S&P 500"),("QQQ","Nasdaq"),("DIA","Dow Jones"),("IWM","Russell 2K"),
    ("AAPL","Apple"),("MSFT","Microsoft"),("NVDA","NVIDIA"),("TSLA","Tesla"),
    ("META","Meta"),("GOOGL","Google"),("AMZN","Amazon"),("JPM","JPMorgan"),
]

def get_market_bar():
    items=[]
    for t,n in MARKET_TICKERS:
        try:
            d=yf.Ticker(t).history(period="2d")
            if len(d)>=2:
                p,pr=round(d["Close"].iloc[-1],2),round(d["Close"].iloc[-2],2)
                items.append({"name":n,"ticker":t,"price":p,"change":round(((p-pr)/pr)*100,2)})
        except: pass
    return items


CSS = """
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0;}
:root{
--bg:#080b14;--surface:#0d1220;--surface2:#111827;--border:#1e2d45;--border2:#243552;
--indigo:#6366f1;--indigo-l:#818cf8;--violet:#8b5cf6;
--vir:#2d9e7a;--vir-l:#34d399;--pine:#166553;
--danger:#f43f5e;--warn:#f59e0b;
--text:#e2e8f0;--text2:#94a3b8;--text3:#475569;
--sw:240px;--r:14px;--rs:8px;
}
html,body{height:100%;overflow-x:hidden;}
body{font-family:Outfit,sans-serif;background:var(--bg);color:var(--text);display:flex;min-height:100vh;}
/* sidebar */
.sb{width:var(--sw);min-height:100vh;background:var(--surface);border-right:1px solid var(--border);display:flex;flex-direction:column;position:fixed;left:0;top:0;bottom:0;z-index:200;transition:transform .3s ease;}
.sb-logo{padding:24px 18px 18px;border-bottom:1px solid var(--border);display:flex;align-items:center;gap:10px;}
.lm{width:36px;height:36px;background:linear-gradient(135deg,var(--indigo),var(--vir));border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:18px;flex-shrink:0;box-shadow:0 0 20px rgba(99,102,241,.4);}
.lt{font-size:19px;font-weight:800;letter-spacing:-.5px;background:linear-gradient(135deg,var(--indigo-l),var(--vir-l));-webkit-background-clip:text;-webkit-text-fill-color:transparent;}
.ls{font-size:9px;color:var(--text3);text-transform:uppercase;letter-spacing:2px;margin-top:1px;-webkit-text-fill-color:var(--text3);}
.sb-nav{flex:1;padding:14px 10px;display:flex;flex-direction:column;gap:2px;}
.nav-s{font-size:9px;text-transform:uppercase;letter-spacing:2px;color:var(--text3);padding:10px 8px 4px;}
.ni{display:flex;align-items:center;gap:10px;padding:10px 12px;border-radius:var(--rs);color:var(--text2);text-decoration:none;font-size:14px;font-weight:500;transition:all .15s;position:relative;cursor:pointer;border:none;background:none;width:100%;text-align:left;font-family:Outfit,sans-serif;}
.ni:hover{background:rgba(99,102,241,.08);color:var(--text);}
.ni.active{background:linear-gradient(135deg,rgba(99,102,241,.15),rgba(45,158,122,.1));color:var(--indigo-l);border:1px solid rgba(99,102,241,.2);}
.ni.active::before{content:'';position:absolute;left:0;top:20%;bottom:20%;width:3px;background:linear-gradient(180deg,var(--indigo),var(--vir));border-radius:0 3px 3px 0;}
.ni-ic{font-size:16px;width:20px;text-align:center;}
.sb-foot{padding:14px 10px;border-top:1px solid var(--border);}
.uc{display:flex;align-items:center;gap:10px;padding:10px 12px;background:var(--surface2);border-radius:var(--rs);border:1px solid var(--border);}
.ua{width:32px;height:32px;background:linear-gradient(135deg,#3730a3,var(--pine));border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:700;color:white;flex-shrink:0;}
.un{font-size:13px;font-weight:600;}
.ur{font-size:10px;color:var(--text3);}
.lo{display:flex;align-items:center;gap:8px;padding:8px 12px;color:var(--text3);font-size:12px;text-decoration:none;border-radius:var(--rs);margin-top:6px;transition:all .15s;}
.lo:hover{color:var(--danger);background:rgba(244,63,94,.08);}
/* overlay for mobile sidebar */
.sb-overlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:190;}
.sb-overlay.show{display:block;}
/* main */
.main{margin-left:var(--sw);flex:1;display:flex;flex-direction:column;min-height:100vh;}
/* market bar */
.mbar{display:flex;overflow-x:auto;scrollbar-width:none;border-bottom:1px solid var(--border);background:var(--surface);}
.mbar::-webkit-scrollbar{display:none;}
.mi{padding:9px 18px;display:flex;align-items:center;gap:10px;border-right:1px solid var(--border);flex-shrink:0;font-size:12px;white-space:nowrap;}
.mn{color:var(--text3);font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:1px;}
.mp{font-weight:700;font-family:'JetBrains Mono',monospace;}
/* page layout */
.ph{padding:28px 32px 20px;border-bottom:1px solid var(--border);background:rgba(13,18,32,.85);backdrop-filter:blur(12px);position:sticky;top:0;z-index:50;}
.pt{font-size:24px;font-weight:800;letter-spacing:-.5px;background:linear-gradient(135deg,var(--text),var(--text2));-webkit-background-clip:text;-webkit-text-fill-color:transparent;}
.ps{font-size:13px;color:var(--text3);margin-top:2px;}
.pb{padding:28px 32px;flex:1;}
/* cards */
.card{background:var(--surface);border:1px solid var(--border);border-radius:var(--r);padding:22px;position:relative;overflow:hidden;}
.card::before{content:'';position:absolute;top:0;left:0;right:0;height:1px;background:linear-gradient(90deg,transparent,rgba(99,102,241,.3),transparent);}
.ct{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:2px;color:var(--text3);margin-bottom:14px;}
/* stats */
.sg{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:14px;margin-bottom:24px;}
.sc{background:var(--surface);border:1px solid var(--border);border-radius:var(--r);padding:18px;transition:border-color .2s,transform .2s;position:relative;overflow:hidden;}
.sc:hover{border-color:var(--border2);transform:translateY(-1px);}
.sl{font-size:10px;color:var(--text3);text-transform:uppercase;letter-spacing:1.5px;font-weight:600;}
.sv{font-size:26px;font-weight:800;margin-top:6px;letter-spacing:-1px;font-family:'JetBrains Mono',monospace;}
.ss{font-size:11px;color:var(--text3);margin-top:3px;}
.up{color:var(--vir-l);}.down{color:var(--danger);}.neu{color:var(--indigo-l);}
/* buttons */
.btn{display:inline-flex;align-items:center;gap:7px;padding:10px 18px;border-radius:var(--rs);font-size:13px;font-weight:600;cursor:pointer;border:none;font-family:Outfit,sans-serif;transition:all .15s;text-decoration:none;white-space:nowrap;}
.bp{background:linear-gradient(135deg,var(--indigo),var(--violet));color:#fff;box-shadow:0 4px 16px rgba(99,102,241,.3);}
.bp:hover{transform:translateY(-1px);box-shadow:0 6px 20px rgba(99,102,241,.4);}
.bg2{background:linear-gradient(135deg,var(--pine),var(--vir));color:#fff;box-shadow:0 4px 16px rgba(45,158,122,.3);}
.bg2:hover{transform:translateY(-1px);}
.bo{background:transparent;color:var(--indigo-l);border:1px solid var(--border2);}
.bo:hover{background:rgba(99,102,241,.08);border-color:var(--indigo);}
.bd{background:rgba(244,63,94,.1);color:var(--danger);border:1px solid rgba(244,63,94,.2);}
.bd:hover{background:rgba(244,63,94,.2);}
.btn:disabled{opacity:.4;cursor:not-allowed;transform:none!important;}
.bblock{width:100%;justify-content:center;}
/* inputs */
.inp{width:100%;padding:10px 13px;background:var(--surface2);border:1px solid var(--border);border-radius:var(--rs);color:var(--text);font-size:14px;font-family:Outfit,sans-serif;outline:none;transition:border-color .15s,box-shadow .15s;}
.inp:focus{border-color:rgba(99,102,241,.5);box-shadow:0 0 0 3px rgba(99,102,241,.1);}
.inp::placeholder{color:var(--text3);}
.inp:-webkit-autofill,.inp:-webkit-autofill:hover,.inp:-webkit-autofill:focus{-webkit-box-shadow:0 0 0 30px #111827 inset!important;-webkit-text-fill-color:var(--text)!important;transition:background-color 9999s ease-in-out 0s;}
.fl{font-size:10px;text-transform:uppercase;letter-spacing:1.5px;color:var(--text3);margin-bottom:5px;font-weight:700;display:block;}
/* stock cards */
.sg2{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:14px;}
.stk{background:var(--surface);border-radius:var(--r);padding:18px;border:1px solid var(--border);transition:all .2s;cursor:pointer;position:relative;overflow:hidden;}
.stk:hover{border-color:var(--border2);transform:translateY(-2px);box-shadow:0 8px 32px rgba(0,0,0,.3);}
.stk.bull{border-top:2px solid var(--vir);}
.stk.bear{border-top:2px solid var(--danger);}
.sh{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:12px;}
.sticker{font-size:21px;font-weight:800;letter-spacing:-.5px;}
.bdg{font-size:10px;font-weight:700;padding:3px 9px;border-radius:20px;letter-spacing:.5px;text-transform:uppercase;}
.bbull{background:rgba(52,211,153,.12);color:var(--vir-l);border:1px solid rgba(52,211,153,.2);}
.bbear{background:rgba(244,63,94,.12);color:var(--danger);border:1px solid rgba(244,63,94,.2);}
.bhigh{background:rgba(99,102,241,.12);color:var(--indigo-l);border:1px solid rgba(99,102,241,.2);}
.bwarn{background:rgba(245,158,11,.12);color:var(--warn);border:1px solid rgba(245,158,11,.2);}
.sprice{font-size:24px;font-weight:800;font-family:'JetBrains Mono',monospace;letter-spacing:-1px;}
.schg{font-size:11px;margin-top:2px;font-family:'JetBrains Mono',monospace;}
.sstats{display:grid;grid-template-columns:1fr 1fr;gap:7px;margin-top:12px;}
.ms{background:var(--surface2);border-radius:6px;padding:7px 9px;}
.ml{font-size:9px;text-transform:uppercase;letter-spacing:1px;color:var(--text3);}
.mv{font-size:13px;font-weight:700;font-family:'JetBrains Mono',monospace;margin-top:2px;}
.pb2{height:4px;background:var(--surface2);border-radius:4px;overflow:hidden;margin-top:9px;}
/* tables */
.tw{overflow-x:auto;border-radius:var(--r);border:1px solid var(--border);}
table{width:100%;border-collapse:collapse;}
th{padding:11px 14px;font-size:9px;text-transform:uppercase;letter-spacing:1.5px;color:var(--text3);text-align:left;background:var(--surface2);font-weight:700;border-bottom:1px solid var(--border);}
td{padding:13px 14px;font-size:12px;border-bottom:1px solid rgba(30,45,69,.5);font-family:'JetBrains Mono',monospace;color:var(--text2);}
tr:last-child td{border-bottom:none;}
tr:hover td{background:rgba(99,102,241,.03);}
/* modal */
.mo{display:none;position:fixed;inset:0;background:rgba(0,0,0,.75);backdrop-filter:blur(4px);z-index:999;padding:20px;overflow-y:auto;align-items:center;justify-content:center;}
.mo.open{display:flex;}
.mb{background:var(--surface);border:1px solid var(--border2);border-radius:var(--r);padding:26px;width:100%;max-width:900px;margin:auto;position:relative;animation:mIn .2s ease;}
@keyframes mIn{from{opacity:0;transform:scale(.96) translateY(10px);}to{opacity:1;transform:scale(1) translateY(0);}}
.mc{position:absolute;top:14px;right:14px;background:var(--surface2);border:1px solid var(--border);border-radius:6px;padding:4px 10px;color:var(--text3);cursor:pointer;font-size:12px;transition:all .15s;}
.mc:hover{color:var(--danger);border-color:var(--danger);}
/* tag */
.tag{display:inline-flex;align-items:center;gap:4px;padding:3px 10px;border-radius:20px;font-size:11px;font-weight:600;background:rgba(99,102,241,.1);color:var(--indigo-l);border:1px solid rgba(99,102,241,.2);cursor:pointer;transition:all .15s;}
.tag:hover{background:rgba(244,63,94,.1);color:var(--danger);border-color:rgba(244,63,94,.2);}
/* chart period bar */
.cbar{display:flex;gap:3px;flex-wrap:wrap;margin-bottom:14px;}
.cp{padding:5px 10px;border-radius:6px;font-size:11px;font-weight:600;cursor:pointer;border:1px solid var(--border);background:none;color:var(--text3);font-family:Outfit,sans-serif;transition:all .15s;}
.cp:hover{border-color:var(--indigo);color:var(--indigo-l);}
.cp.active{background:rgba(99,102,241,.15);border-color:var(--indigo);color:var(--indigo-l);}
/* animate */
@keyframes fup{from{opacity:0;transform:translateY(14px);}to{opacity:1;transform:translateY(0);}}
.fi{animation:fup .4s ease both;}
.fi1{animation-delay:.05s;}.fi2{animation-delay:.1s;}.fi3{animation-delay:.15s;}
::-webkit-scrollbar{width:5px;height:5px;}
::-webkit-scrollbar-track{background:transparent;}
::-webkit-scrollbar-thumb{background:var(--border2);border-radius:3px;}
/* mobile */
@media(max-width:768px){
  :root{--sw:0px;}
  .sb{transform:translateX(-240px);width:240px;}
  .sb.open{transform:translateX(0);}
  .main{margin-left:0;}
  .pb{padding:18px 14px;}
  .ph{padding:18px 14px 14px;}
  .sg{grid-template-columns:1fr 1fr;}
  .sg2{grid-template-columns:1fr;}
  .mt-btn{display:flex!important;}
  .ph-row{flex-direction:column!important;align-items:flex-start!important;gap:10px!important;}
}
.mt-btn{display:none;position:fixed;top:14px;right:14px;z-index:300;background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:7px 12px;cursor:pointer;color:var(--text);font-size:16px;align-items:center;gap:6px;font-size:13px;font-weight:600;font-family:Outfit,sans-serif;}
"""

CHART_MODAL = """
<div class="mo" id="chartModal">
<div class="mb" style="max-width:940px;">
<button class="mc" onclick="closeChart()">✕ Close</button>
<div id="cmTitle" style="font-size:19px;font-weight:800;margin-bottom:4px;letter-spacing:-.5px;"></div>
<div style="font-size:11px;color:var(--text3);margin-bottom:14px;">Candlestick · MA20 · MA50 · MA200 · Volume</div>
<div class="cbar" id="periodBar">
  <button class="cp" onclick="setPeriod('1mo')">1M</button>
  <button class="cp" onclick="setPeriod('3mo')">3M</button>
  <button class="cp active" onclick="setPeriod('6mo')">6M</button>
  <button class="cp" onclick="setPeriod('ytd')">YTD</button>
  <button class="cp" onclick="setPeriod('1y')">1Y</button>
  <button class="cp" onclick="setPeriod('5y')">5Y</button>
  <button class="cp" onclick="setPeriod('max')">MAX</button>
</div>
<div id="chartContainer" style="height:360px;border-radius:10px;overflow:hidden;background:var(--surface2);"></div>
<div id="volContainer" style="height:90px;border-radius:10px;overflow:hidden;background:var(--surface2);margin-top:5px;"></div>
<div style="display:flex;gap:16px;margin-top:10px;font-size:11px;color:var(--text3);flex-wrap:wrap;">
  <span>&#9644; <span style="color:#22d3ee">MA20</span></span>
  <span>&#9644; <span style="color:#f59e0b">MA50</span></span>
  <span>&#9644; <span style="color:#8b5cf6">MA200</span></span>
  <span style="color:var(--vir-l);">&#9646; Bull candle</span>
  <span style="color:var(--danger);">&#9646; Bear candle</span>
</div>
</div></div>"""

CHART_JS = """
<script src="https://unpkg.com/lightweight-charts@4.1.3/dist/lightweight-charts.standalone.production.js"></script>
<script>
var _cTicker='', _cPeriod='6mo', _chart=null, _vchart=null;
function buildChart(ticker){
    _cTicker=ticker;
    document.getElementById('cmTitle').textContent=ticker;
    document.getElementById('chartModal').classList.add('open');
    loadChart();
}
function setPeriod(p){
    _cPeriod=p;
    document.querySelectorAll('.cp').forEach(b=>b.classList.toggle('active',b.textContent.toLowerCase()===p||
        (p==='1mo'&&b.textContent==='1M')||(p==='3mo'&&b.textContent==='3M')||(p==='6mo'&&b.textContent==='6M')||
        (p==='ytd'&&b.textContent==='YTD')||(p==='1y'&&b.textContent==='1Y')||(p==='5y'&&b.textContent==='5Y')||
        (p==='max'&&b.textContent==='MAX')));
    loadChart();
}
function loadChart(){
    var ce=document.getElementById('chartContainer'),ve=document.getElementById('volContainer');
    ce.innerHTML='<div style="display:flex;align-items:center;justify-content:center;height:100%;color:var(--text3);font-size:13px;">Loading...</div>';
    ve.innerHTML='';
    if(_chart){try{_chart.remove();}catch(e){} _chart=null;}
    if(_vchart){try{_vchart.remove();}catch(e){} _vchart=null;}
    fetch('/chart?ticker='+_cTicker+'&period='+_cPeriod).then(r=>r.json()).then(data=>{
        ce.innerHTML='';
        _chart=LightweightCharts.createChart(ce,{width:ce.clientWidth,height:360,
            layout:{background:{color:'transparent'},textColor:'#94a3b8'},
            grid:{vertLines:{color:'rgba(30,45,69,.5)'},horzLines:{color:'rgba(30,45,69,.5)'}},
            crosshair:{mode:LightweightCharts.CrosshairMode.Normal},
            rightPriceScale:{borderColor:'rgba(30,45,69,.8)'},
            timeScale:{borderColor:'rgba(30,45,69,.8)',timeVisible:true}});
        var cs=_chart.addCandlestickSeries({upColor:'#34d399',downColor:'#f43f5e',
            borderUpColor:'#34d399',borderDownColor:'#f43f5e',wickUpColor:'#34d399',wickDownColor:'#f43f5e'});
        cs.setData(data.candles);
        _chart.addLineSeries({color:'#22d3ee',lineWidth:1,title:'MA20'}).setData(data.ma20);
        _chart.addLineSeries({color:'#f59e0b',lineWidth:1.5,title:'MA50'}).setData(data.ma50);
        _chart.addLineSeries({color:'#8b5cf6',lineWidth:1.5,lineStyle:1,title:'MA200'}).setData(data.ma200);
        _vchart=LightweightCharts.createChart(ve,{width:ve.clientWidth,height:90,
            layout:{background:{color:'transparent'},textColor:'#94a3b8'},
            grid:{vertLines:{color:'rgba(30,45,69,.3)'},horzLines:{visible:false}},
            rightPriceScale:{borderColor:'rgba(30,45,69,.8)'},
            timeScale:{borderColor:'rgba(30,45,69,.8)',visible:false}});
        var vs=_vchart.addHistogramSeries({priceFormat:{type:'volume'},priceScaleId:''});
        vs.priceScale().applyOptions({scaleMargins:{top:.1,bottom:0}});
        vs.setData(data.volumes);
        _chart.timeScale().subscribeVisibleLogicalRangeChange(r=>{if(r)_vchart.timeScale().setVisibleLogicalRange(r);});
        _chart.timeScale().fitContent();
    });
}
function closeChart(){
    document.getElementById('chartModal').classList.remove('open');
    _cTicker='';_cPeriod='6mo';
    if(_chart){try{_chart.remove();}catch(e){} _chart=null;}
    if(_vchart){try{_vchart.remove();}catch(e){} _vchart=null;}
    document.getElementById('chartContainer').innerHTML='';
    document.getElementById('volContainer').innerHTML='';
}
</script>"""

def sidebar(active):
    u=me(); ini=u[0].upper() if u else "?"
    pages=[("home","🏠","Home","/"),("trading","🤖","Paper Trading","/trading"),
           ("registry","📊","Share Registry","/registry"),("alerts","🔔","Alerts","/alerts")]
    nav="".join([f'<a href="{href}" class="ni {"active" if active==pid else ""}"><span class="ni-ic">{ic}</span>{lb}</a>'
                 for pid,ic,lb,href in pages])
    return f"""
<button class="mt-btn" onclick="toggleSB()">☰ Menu</button>
<div class="sb-overlay" id="sbo" onclick="closeSB()"></div>
<aside class="sb" id="sb">
  <div class="sb-logo">
    <div class="lm">⚡</div>
    <div><a href="/" style="text-decoration:none;"><div class="lt">VULCAN</div></a><div class="ls">Trading Intelligence</div></div>
  </div>
  <nav class="sb-nav"><div class="nav-s">Navigation</div>{nav}</nav>
  <div class="sb-foot">
    <div class="uc">
      <div class="ua">{ini}</div>
      <div><div class="un">{u}</div><div class="ur">Trader</div></div>
    </div>
    <a href="/logout" class="lo">↩ Sign out</a>
  </div>
</aside>
<script>
function toggleSB(){{document.getElementById('sb').classList.toggle('open');document.getElementById('sbo').classList.toggle('show');}}
function closeSB(){{document.getElementById('sb').classList.remove('open');document.getElementById('sbo').classList.remove('show');}}
</script>"""

def mbar_html(items):
    h=""
    for m in items:
        c="up" if m["change"]>=0 else "down"
        s="▲" if m["change"]>=0 else "▼"
        h+=f'<div class="mi"><div><div class="mn">{m["name"]}</div><div class="mp">${m["price"]}</div></div><span class="{c}" style="font-size:11px;font-family:\'JetBrains Mono\',monospace;">{s} {abs(m["change"])}%</span></div>'
    return h


LOGIN_PAGE = """<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Vulcan — Sign In</title>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
{CSS}
body{background:var(--bg);display:flex;align-items:center;justify-content:center;min-height:100vh;position:relative;overflow:hidden;}
.orb{position:fixed;border-radius:50%;filter:blur(80px);opacity:.13;animation:float 8s ease-in-out infinite;pointer-events:none;}
.orb1{width:500px;height:500px;background:var(--indigo);top:-150px;left:-150px;}
.orb2{width:400px;height:400px;background:var(--vir);bottom:-100px;right:-100px;animation-delay:-3s;}
.orb3{width:300px;height:300px;background:var(--violet);top:40%;left:50%;animation-delay:-6s;}
@keyframes float{0%,100%{transform:translate(0,0) scale(1);}33%{transform:translate(20px,-20px) scale(1.05);}66%{transform:translate(-10px,15px) scale(.97);}}
.bgrid{position:fixed;inset:0;background-image:linear-gradient(rgba(99,102,241,.04) 1px,transparent 1px),linear-gradient(90deg,rgba(99,102,241,.04) 1px,transparent 1px);background-size:48px 48px;pointer-events:none;}
.wrap{width:100%;max-width:440px;padding:20px;position:relative;z-index:10;animation:fup .5s ease both;}
@keyframes fup{from{opacity:0;transform:translateY(24px);}to{opacity:1;transform:translateY(0);}}
.lmark{width:64px;height:64px;background:linear-gradient(135deg,var(--indigo),var(--vir));border-radius:18px;display:flex;align-items:center;justify-content:center;font-size:28px;margin:0 auto 14px;box-shadow:0 0 40px rgba(99,102,241,.4),0 0 80px rgba(45,158,122,.2);animation:glow 3s ease-in-out infinite;}
@keyframes glow{0%,100%{box-shadow:0 0 30px rgba(99,102,241,.3),0 0 60px rgba(45,158,122,.15);}50%{box-shadow:0 0 50px rgba(99,102,241,.5),0 0 100px rgba(45,158,122,.25);}}
.lcard{background:rgba(13,18,32,.9);border:1px solid var(--border);border-radius:20px;padding:32px;backdrop-filter:blur(20px);position:relative;overflow:hidden;}
.lcard::before{content:'';position:absolute;top:0;left:10%;right:10%;height:1px;background:linear-gradient(90deg,transparent,rgba(99,102,241,.5),rgba(45,158,122,.3),transparent);}
.tabs{display:grid;grid-template-columns:1fr 1fr;gap:4px;background:var(--surface2);border-radius:10px;padding:4px;margin-bottom:24px;}
.tab{padding:9px;text-align:center;border-radius:7px;cursor:pointer;font-size:13px;font-weight:600;color:var(--text3);transition:all .2s;border:none;background:none;font-family:Outfit,sans-serif;}
.tab.active{background:linear-gradient(135deg,rgba(99,102,241,.15),rgba(45,158,122,.1));color:var(--indigo-l);border:1px solid rgba(99,102,241,.25);}
.fg{margin-bottom:16px;}
.err{background:rgba(244,63,94,.08);border:1px solid rgba(244,63,94,.25);border-radius:9px;padding:11px 14px;font-size:13px;color:var(--danger);margin-bottom:16px;display:none;}
.err.show{display:block;animation:shake .3s ease;}
@keyframes shake{0%,100%{transform:translateX(0);}25%{transform:translateX(-5px);}75%{transform:translateX(5px);}}
.ok2{background:rgba(52,211,153,.08);border:1px solid rgba(52,211,153,.25);border-radius:9px;padding:11px 14px;font-size:13px;color:var(--vir-l);margin-bottom:16px;display:none;}
.ok2.show{display:block;}
.lbtn{width:100%;padding:13px;background:linear-gradient(135deg,var(--indigo),var(--violet));color:#fff;border:none;border-radius:9px;font-size:14px;font-weight:700;font-family:Outfit,sans-serif;cursor:pointer;margin-top:6px;transition:all .2s;box-shadow:0 4px 20px rgba(99,102,241,.3);}
.lbtn:hover{transform:translateY(-1px);box-shadow:0 8px 28px rgba(99,102,241,.4);}
.lbtn:disabled{opacity:.5;transform:none;cursor:not-allowed;}
</style></head>
<body>
<div class="orb orb1"></div><div class="orb orb2"></div><div class="orb orb3"></div>
<div class="bgrid"></div>
<div class="wrap">
  <div style="text-align:center;margin-bottom:28px;">
    <div class="lmark">⚡</div>
    <h1 style="font-size:32px;font-weight:800;letter-spacing:-1px;background:linear-gradient(135deg,var(--indigo-l),var(--vir-l));-webkit-background-clip:text;-webkit-text-fill-color:transparent;">VULCAN</h1>
    <p style="font-size:11px;color:var(--text3);letter-spacing:3px;text-transform:uppercase;margin-top:4px;">Trading Intelligence</p>
  </div>
  <div class="lcard">
    <div class="tabs">
      <button class="tab active" onclick="switchTab('login')">Sign In</button>
      <button class="tab" onclick="switchTab('register')">Register</button>
    </div>
    <div id="errBox" class="err"></div>
    <div id="okBox"  class="ok2"></div>
    <form id="loginForm" onsubmit="doLogin(event)" autocomplete="on">
      <div class="fg"><label class="fl">Username</label><input type="text" id="lu" class="inp" placeholder="your_username" autocomplete="username" required></div>
      <div class="fg"><label class="fl">Password</label><input type="password" id="lp" class="inp" placeholder="••••••••" autocomplete="current-password" required></div>
      <button type="submit" class="lbtn" id="lbtn">Access Dashboard →</button>
    </form>
    <form id="regForm" onsubmit="doReg(event)" autocomplete="on" style="display:none;">
      <div class="fg"><label class="fl">Username</label><input type="text" id="ru" class="inp" placeholder="choose_a_username" autocomplete="username" required></div>
      <div class="fg"><label class="fl">Password</label><input type="password" id="rp" class="inp" placeholder="min. 6 characters" autocomplete="new-password" required></div>
      <div class="fg"><label class="fl">Confirm Password</label><input type="password" id="rc" class="inp" placeholder="repeat password" autocomplete="new-password" required></div>
      <button type="submit" class="lbtn" id="rbtn">Create Account →</button>
    </form>
    <div style="text-align:center;margin-top:18px;font-size:11px;color:var(--text3);line-height:1.7;">Paper trading · ML signals · Community registry</div>
  </div>
</div>
<script>
function switchTab(t){
  ['login','register'].forEach((x,i)=>{
    document.querySelectorAll('.tab')[i].classList.toggle('active',x===t);
    document.getElementById(x==='login'?'loginForm':'regForm').style.display=x===t?'block':'none';
  });
  clrMsg();
}
function showErr(m){var e=document.getElementById('errBox');e.textContent='⚠ '+m;e.className='err show';document.getElementById('okBox').className='ok2';}
function showOk(m){var e=document.getElementById('okBox');e.textContent='✓ '+m;e.className='ok2 show';document.getElementById('errBox').className='err';}
function clrMsg(){document.getElementById('errBox').className='err';document.getElementById('okBox').className='ok2';}
async function doLogin(e){
  e.preventDefault();
  var btn=document.getElementById('lbtn');btn.disabled=true;btn.textContent='Authenticating...';clrMsg();
  var r=await fetch('/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({username:document.getElementById('lu').value.trim(),password:document.getElementById('lp').value})});
  var d=await r.json();
  if(d.success){btn.textContent='✓ Redirecting...';window.location.href='/';}
  else{showErr(d.error);btn.disabled=false;btn.textContent='Access Dashboard →';}
}
async function doReg(e){
  e.preventDefault();
  var p=document.getElementById('rp').value,c=document.getElementById('rc').value;
  clrMsg();
  if(p!==c){showErr("Passwords don't match.");return;}
  if(p.length<6){showErr("Password must be at least 6 characters.");return;}
  var btn=document.getElementById('rbtn');btn.disabled=true;btn.textContent='Creating...';
  var r=await fetch('/auth/register',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({username:document.getElementById('ru').value.trim(),password:p})});
  var d=await r.json();
  if(d.success){showOk('Account created! Sign in now.');setTimeout(()=>switchTab('login'),1500);}
  else showErr(d.error);
  btn.disabled=false;btn.textContent='Create Account →';
}
</script></body></html>"""


@app.route("/login")
def login():
    if logged_in(): return redirect(url_for("home"))
    return LOGIN_PAGE.replace("{CSS}", CSS)

@app.route("/logout")
def logout():
    session.clear(); return redirect(url_for("login"))

@app.route("/auth/login", methods=["POST"])
def auth_login():
    data=request.json
    u=data.get("username","").strip().lower()
    p=data.get("password","")
    if not u or not p: return jsonify({"success":False,"error":"Username and password required."})
    users=load_users()
    if u not in users or users[u]["password"]!=hash_pw(p):
        return jsonify({"success":False,"error":"Invalid username or password."})
    session["username"]=u; session.permanent=True
    return jsonify({"success":True})

@app.route("/auth/register", methods=["POST"])
def auth_register():
    data=request.json
    u=data.get("username","").strip().lower()
    p=data.get("password","")
    if not u or not p: return jsonify({"success":False,"error":"All fields required."})
    if len(u)<3: return jsonify({"success":False,"error":"Username: min 3 characters."})
    if not u.replace("_","").replace("-","").isalnum(): return jsonify({"success":False,"error":"Letters, numbers, - and _ only."})
    users=load_users()
    if u in users: return jsonify({"success":False,"error":"Username already taken."})
    users[u]={"password":hash_pw(p),"created":datetime.now().isoformat()}
    save_users(users); return jsonify({"success":True})

@app.route("/")
def home():
    if not logged_in(): return redirect(url_for("login"))
    watchlist=load_watchlist()
    stocks=[d for t in watchlist for d in [analyze_stock(t)] if d]
    market=get_market_bar()

    cards=""
    for s in stocks:
        bull=s["prediction"]==1
        pp=int(s.get("proba",.5)*100)
        chg=s.get("change_pct",0)
        cc="up" if chg>=0 else "down"
        grade_cls="bhigh" if s["confidence"]=="High" else "bwarn"
        cards+=f"""<div class="stk {"bull" if bull else "bear"}" onclick="buildChart('{s["ticker"]}')">
  <div class="sh">
    <div><div class="sticker">{s["ticker"]}</div></div>
    <div style="display:flex;flex-direction:column;align-items:flex-end;gap:4px;">
      <span class="bdg {"bbull" if bull else "bbear"}">{"↑ BUY" if bull else "↓ SELL"}</span>
      <span class="bdg {grade_cls}">{s["confidence"]}</span>
    </div>
  </div>
  <div class="sprice">${s["price"]}</div>
  <div class="schg {cc}">{("+" if chg>=0 else "")}{chg}% today</div>
  <div class="sstats">
    <div class="ms"><div class="ml">RSI</div><div class="mv {"down" if s["rsi"]>70 else "up" if s["rsi"]<30 else ""}">{s["rsi"]}</div></div>
    <div class="ms"><div class="ml">MA20</div><div class="mv">{s["ma20"]}</div></div>
    <div class="ms"><div class="ml">MA50</div><div class="mv">{s["ma50"]}</div></div>
    <div class="ms"><div class="ml">Signal</div><div class="mv {"up" if bull else "down"}">{pp}%</div></div>
  </div>
  <div class="pb2"><div style="height:100%;border-radius:4px;width:{pp}%;background:linear-gradient(90deg,{"var(--vir)" if bull else "var(--danger)"},{"var(--indigo-l)" if bull else "var(--violet)"});"></div></div>
  <div style="margin-top:10px;font-size:10px;color:var(--text3);">{'RSI oversold — potential reversal' if s['rsi']<30 else 'RSI overbought — watch for pullback' if s['rsi']>70 else 'MA50 above MA200 — bullish trend' if s['ma50']>s['ma200'] else 'MA50 below MA200 — bearish trend'}</div>
</div>"""

    wl_tags="".join([f'<span class="tag" onclick="removeStock(\'{t}\')">{t} ×</span>' for t in watchlist])

    html=f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Vulcan — Home</title>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>{CSS}</style></head>
<body>{sidebar("home")}
<div class="main">
<div class="mbar">{mbar_html(market)}</div>
<div class="ph" style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px;">
  <div><div class="pt">Market Overview</div><div class="ps">Watchlist signals · Stock search · AI recommendations</div></div>
</div>
<div class="pb">
  <div class="card fi" style="margin-bottom:20px;">
    <div class="ct">🔍 Stock Search</div>
    <div style="display:flex;gap:10px;"><input type="text" id="si" class="inp" placeholder="Enter any ticker (e.g. TSLA) and press Enter" style="flex:1;"><button class="btn bp" onclick="doSearch()">Analyze</button></div>
    <div id="sr" style="margin-top:14px;"></div>
  </div>
  <div class="card fi fi1" style="margin-bottom:20px;">
    <div class="ct">📋 Watchlist</div>
    <p style="font-size:12px;color:var(--text3);margin-bottom:12px;">Stocks you're tracking. Click any card to see the full chart.</p>
    <div style="display:flex;gap:8px;margin-bottom:12px;flex-wrap:wrap;"><input type="text" id="ai" class="inp" placeholder="Add ticker..." style="max-width:160px;"><button class="btn bg2" onclick="addStock()">+ Add</button></div>
    <div style="display:flex;flex-wrap:wrap;gap:6px;">{wl_tags}</div>
  </div>
  <div class="card fi fi2" style="margin-bottom:20px;">
    <div class="ct">⚡ AI Recommendations</div>
    <p style="font-size:12px;color:var(--text3);margin-bottom:12px;">Scans 15 major stocks using the ML model and surfaces the strongest buy/sell signals right now.</p>
    <button class="btn bo bblock" onclick="getRecs()" id="recBtn" style="padding:12px;">⚡ Scan Market Now</button>
    <div id="recResult" style="margin-top:14px;"></div>
  </div>
  <div class="ct fi fi2" style="margin-bottom:14px;">Watchlist Signals</div>
  <div class="sg2 fi fi3">{cards}</div>
</div></div>
{CHART_MODAL}{CHART_JS}
<script>
document.getElementById('si').addEventListener('keydown',e=>{{if(e.key==='Enter')doSearch();}});
function doSearch(){{
  var t=document.getElementById('si').value.trim().toUpperCase();if(!t)return;
  var el=document.getElementById('sr');
  el.innerHTML='<div style="color:var(--text3);font-size:13px;padding:10px 0;">Analyzing '+t+'...</div>';
  fetch('/search?ticker='+t).then(r=>r.json()).then(d=>{{
    if(d.error){{el.innerHTML='<div style="color:var(--danger);padding:10px 0;">Could not find '+t+'. Make sure it is a valid ticker symbol.</div>';return;}}
    var bull=d.prediction===1,p=Math.round((d.proba||.5)*100);
    el.innerHTML=`<div style="background:var(--surface2);border:1px solid var(--border);border-radius:12px;padding:18px;display:flex;flex-wrap:wrap;gap:16px;align-items:center;justify-content:space-between;">
      <div><div style="font-size:20px;font-weight:800;cursor:pointer;" onclick="buildChart('${{d.ticker}}')">${{d.ticker}} <span style="font-size:12px;color:var(--indigo-l);">→ view chart</span></div>
      <div style="font-size:26px;font-weight:800;font-family:'JetBrains Mono',monospace;margin-top:4px;">$$${{d.price}}</div>
      <div style="font-size:11px;color:var(--text3);margin-top:2px;">RSI ${{d.rsi}} · MA50 $$${{d.ma50}} · MA200 $$${{d.ma200}}</div></div>
      <div style="display:flex;flex-direction:column;gap:7px;align-items:flex-end;">
        <span class="bdg ${{bull?'bbull':'bbear'}}">${{bull?'↑ BUY':'↓ SELL'}}</span>
        <span class="bdg bhigh">Confidence: ${{d.confidence}}</span>
        <span style="font-size:11px;color:var(--text3);">Signal strength: ${{p}}%</span>
      </div></div>`;
  }});
}}
function addStock(){{var t=document.getElementById('ai').value.trim().toUpperCase();if(!t)return;fetch('/add_stock',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{ticker:t}})}}).then(()=>location.reload());}}
function removeStock(t){{fetch('/remove_stock',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{ticker:t}})}}).then(()=>location.reload());}}
function getRecs(){{
  var btn=document.getElementById('recBtn'),div=document.getElementById('recResult');
  btn.disabled=true;btn.textContent='⏳ Scanning 15 stocks...';div.innerHTML='';
  fetch('/recommend').then(r=>r.json()).then(data=>{{
    btn.disabled=false;btn.textContent='⚡ Scan Market Now';
    var total=(data.buys||[]).length+(data.sells||[]).length;
    if(total===0){{div.innerHTML='<div style="padding:16px;background:var(--surface2);border-radius:10px;font-size:13px;color:var(--text3);">No high-confidence signals right now. Market may be in a low-volatility phase. Try again later or lower the confidence threshold.</div>';return;}}
    var h='<div class="card"><div class="ct">⚡ AI Recommendations — '+total+' signal'+(total!==1?'s':'')+' found</div>';
    if((data.buys||[]).length){{
      h+='<div style="font-size:12px;font-weight:700;color:var(--vir-l);margin-bottom:9px;">Strong Buy Signals</div>';
      data.buys.forEach(s=>{{h+=`<div style="display:flex;justify-content:space-between;align-items:center;padding:10px 12px;background:var(--surface2);border-radius:8px;margin-bottom:6px;cursor:pointer;border:1px solid rgba(52,211,153,.1);" onclick="buildChart('${{s.ticker}}')"><span style="font-weight:700;">${{s.ticker}}</span><span style="color:var(--text3);font-size:11px;">RSI ${{s.rsi}}</span><span style="font-family:'JetBrains Mono',monospace;font-size:12px;">$$${{s.price}}</span><span class="bdg bbull">↑ ${{s.confidence}}</span></div>`;}});
    }}
    if((data.sells||[]).length){{
      h+='<div style="font-size:12px;font-weight:700;color:var(--danger);margin:12px 0 9px;">Strong Sell Signals</div>';
      data.sells.forEach(s=>{{h+=`<div style="display:flex;justify-content:space-between;align-items:center;padding:10px 12px;background:var(--surface2);border-radius:8px;margin-bottom:6px;cursor:pointer;border:1px solid rgba(244,63,94,.1);" onclick="buildChart('${{s.ticker}}')"><span style="font-weight:700;">${{s.ticker}}</span><span style="color:var(--text3);font-size:11px;">RSI ${{s.rsi}}</span><span style="font-family:'JetBrains Mono',monospace;font-size:12px;">$$${{s.price}}</span><span class="bdg bbear">↓ ${{s.confidence}}</span></div>`;}});
    }}
    h+='</div>';div.innerHTML=h;
  }}).catch(()=>{{btn.disabled=false;btn.textContent='⚡ Scan Market Now';}});
}}
</script></body></html>"""
    return html


@app.route("/trading")
def trading():
    if not logged_in(): return redirect(url_for("login"))
    portfolio=load_portfolio(me())
    starting=portfolio.get("starting_cash",10000)
    cash=portfolio.get("cash",starting)
    positions=portfolio.get("positions",{})
    trades=portfolio.get("trades",[])
    total_pv=0; pos_rows=""
    for ticker,pos in positions.items():
        if pos["shares"]>0:
            try:
                cur=round(yf.Ticker(ticker).history(period="1d")["Close"].iloc[-1],2)
                val=round(pos["shares"]*cur,2); pnl=round((cur-pos["buy_price"])*pos["shares"],2)
                pnl_pct=round(((cur-pos["buy_price"])/pos["buy_price"])*100,2); total_pv+=val
                pc="up" if pnl>=0 else "down"
                pos_rows+=f"<tr><td style='color:var(--text);font-weight:700;cursor:pointer;' onclick=\"buildChart('{ticker}')\">{ticker}</td><td>{pos['shares']}</td><td>${pos['buy_price']}</td><td>${cur}</td><td>${val}</td><td class='{pc}'>{'+' if pnl>=0 else ''}${pnl} ({'+' if pnl_pct>=0 else ''}{pnl_pct}%)</td></tr>"
            except: pass
    if not pos_rows: pos_rows="<tr><td colspan='6' style='color:var(--text3);text-align:center;padding:28px;'>No open positions yet.</td></tr>"
    total=round(cash+total_pv,2); ret=round(((total-starting)/starting)*100,2); rc="up" if ret>=0 else "down"
    trows=""
    for t in reversed(trades[-60:]):
        if isinstance(t,dict):
            ac="up" if t.get("action")=="BUY" else "down"
            pr=f"<td class='up'>+${t.get('profit','')}</td>" if t.get("action")=="SELL" else "<td>—</td>"
            cf=t.get("confidence",""); bc="bhigh" if cf=="High" else "bwarn"
            trows+=f"<tr><td class='{ac}' style='font-weight:700;'>{t.get('action','')}</td><td style='color:var(--text);font-weight:700;cursor:pointer;' onclick=\"buildChart('{t.get('ticker','')}')\">{t.get('ticker','')}</td><td>${t.get('price','')}</td><td>{t.get('shares','')}</td><td>${t.get('total','')}</td>{pr}<td style='color:var(--text3);font-size:10px;'>{t.get('date','')}</td><td><span class='bdg {bc}'>{cf}</span></td></tr>"
        else: trows+=f"<tr><td colspan='8' style='color:var(--text3);'>{t}</td></tr>"
    if not trows: trows="<tr><td colspan='8' style='color:var(--text3);text-align:center;padding:28px;'>No trades yet — run the bot to start.</td></tr>"
    oc=len([p for p in positions.values() if p["shares"]>0])
    cph=round((cash/total)*100,1) if total>0 else 100
    market=get_market_bar()

    html=f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Vulcan — Paper Trading</title>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>{CSS}</style></head>
<body>{sidebar("trading")}
<div class="main">
<div class="mbar">{mbar_html(market)}</div>
<div class="ph">
  <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px;" class="ph-row">
    <div><div class="pt">Paper Trading</div><div class="ps">AI-driven autonomous trading · {me()}'s portfolio · Strategy: balanced</div></div>
    <div style="display:flex;gap:8px;flex-wrap:wrap;">
      <button class="btn bg2" onclick="runBot()" id="runBtn">▶ Run Bot</button>
      <button class="btn bo" onclick="document.getElementById('cashModal').classList.add('open')">💰 Set Cash</button>
      <button class="btn bo" onclick="document.getElementById('stratModal').classList.add('open')">⚙ Strategy</button>
    </div>
  </div>
</div>
<div class="pb">
  <div style="background:rgba(99,102,241,.06);border:1px solid rgba(99,102,241,.15);border-radius:12px;padding:14px 18px;margin-bottom:20px;font-size:13px;color:var(--text2);line-height:1.7;" class="fi">
    ℹ️ <strong style="color:var(--text);">How the bot works:</strong> The bot uses a Random Forest ML model trained on 2 years of price history, RSI, MACD, Bollinger Bands, and moving averages.
    It buys when signal probability exceeds the strategy threshold and sells when conditions reverse. Click <strong style="color:var(--indigo-l);">Run Bot</strong> to trigger a scan, or it can run automatically.
    Use <strong style="color:var(--indigo-l);">Strategy</strong> to change how aggressively it trades.
  </div>
  <div class="sg fi">
    <div class="sc"><div class="sl">Portfolio Value</div><div class="sv {rc}">${total:,.2f}</div><div class="ss">Starting: ${starting:,.2f}</div></div>
    <div class="sc"><div class="sl">Cash Available</div><div class="sv neu">${cash:,.2f}</div><div class="ss">{cph}% of portfolio</div></div>
    <div class="sc"><div class="sl">Total Return</div><div class="sv {rc}">{('+' if ret>=0 else '')}{ret}%</div><div class="ss">P&amp;L: ${round(total-starting,2):+,.2f}</div></div>
    <div class="sc"><div class="sl">Open Positions</div><div class="sv neu">{oc}</div><div class="ss">Total trades: {len(trades)}</div></div>
  </div>
  <div class="card fi fi1" style="margin-bottom:20px;">
    <div class="ct">Open Positions</div>
    <div class="tw"><table><thead><tr><th>Ticker</th><th>Shares</th><th>Avg Cost</th><th>Current</th><th>Value</th><th>P&amp;L</th></tr></thead><tbody>{pos_rows}</tbody></table></div>
  </div>
  <div class="card fi fi2">
    <div class="ct">Trade History (last 60)</div>
    <div class="tw"><table><thead><tr><th>Action</th><th>Ticker</th><th>Price</th><th>Shares</th><th>Total</th><th>Profit</th><th>Date</th><th>Confidence</th></tr></thead><tbody>{trows}</tbody></table></div>
  </div>
</div></div>
<div class="mo" id="cashModal">
  <div class="mb" style="max-width:400px;">
    <button class="mc" onclick="document.getElementById('cashModal').classList.remove('open')">✕</button>
    <div style="font-size:18px;font-weight:800;margin-bottom:6px;">Set Starting Cash</div>
    <div style="font-size:12px;color:var(--text3);margin-bottom:20px;">This resets your paper account — all positions and trades will be cleared.</div>
    <label class="fl">Amount ($)</label>
    <input type="number" id="cashAmt" class="inp" value="{starting}" min="100" style="margin-bottom:14px;">
    <button class="btn bp bblock" onclick="setCash()">Reset Portfolio</button>
  </div>
</div>
<div class="mo" id="stratModal">
  <div class="mb" style="max-width:500px;">
    <button class="mc" onclick="document.getElementById('stratModal').classList.remove('open')">✕</button>
    <div style="font-size:18px;font-weight:800;margin-bottom:6px;">Trading Strategy</div>
    <div style="font-size:12px;color:var(--text3);margin-bottom:20px;">Choose how the bot decides when to buy and sell.</div>
    <div style="display:flex;flex-direction:column;gap:10px;">
      <div onclick="setStrat('aggressive')" style="padding:14px;border-radius:10px;border:1px solid var(--border);cursor:pointer;transition:all .15s;" onmouseover="this.style.borderColor='var(--vir)'" onmouseout="this.style.borderColor='var(--border)'">
        <div style="font-weight:700;color:var(--vir-l);margin-bottom:4px;">🚀 Aggressive</div>
        <div style="font-size:12px;color:var(--text3);">Buys on weaker signals, larger position sizes (35%). More trades, more volatility. Best for bull markets.</div>
      </div>
      <div onclick="setStrat('balanced')" style="padding:14px;border-radius:10px;border:1px solid var(--indigo);cursor:pointer;background:rgba(99,102,241,.05);transition:all .15s;">
        <div style="font-weight:700;color:var(--indigo-l);margin-bottom:4px;">⚖ Balanced (Current)</div>
        <div style="font-size:12px;color:var(--text3);">Moderate signal threshold, balanced position sizes (28%). Good for most market conditions.</div>
      </div>
      <div onclick="setStrat('conservative')" style="padding:14px;border-radius:10px;border:1px solid var(--border);cursor:pointer;transition:all .15s;" onmouseover="this.style.borderColor='var(--warn)'" onmouseout="this.style.borderColor='var(--border)'">
        <div style="font-weight:700;color:var(--warn);margin-bottom:4px;">🛡 Conservative</div>
        <div style="font-size:12px;color:var(--text3);">Only buys on high-confidence signals, smaller positions (20%). Fewer trades, lower risk. Best for volatile markets.</div>
      </div>
    </div>
  </div>
</div>
{CHART_MODAL}{CHART_JS}
<script>
var _strat='balanced';
function runBot(){{var btn=document.getElementById('runBtn');btn.disabled=true;btn.textContent='⏳ Running...';fetch('/run?strategy='+_strat).then(r=>r.json()).then(()=>{{btn.textContent='✓ Done!';setTimeout(()=>location.reload(),900);}}).catch(()=>{{btn.disabled=false;btn.textContent='▶ Run Bot';}});}}
function setCash(){{var a=parseFloat(document.getElementById('cashAmt').value);if(!a||a<100)return;fetch('/set_cash',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{amount:a}})}}).then(()=>location.reload());}}
function setStrat(s){{_strat=s;document.getElementById('stratModal').classList.remove('open');document.querySelector('.ps').textContent='AI-driven autonomous trading · {me()}\\'s portfolio · Strategy: '+s;}}
</script></body></html>"""
    return html


@app.route("/registry")
def registry():
    if not logged_in(): return redirect(url_for("login"))
    reg_data=get_registry_with_flags()
    holdings=load_holdings()
    flagged=sum(1 for r in reg_data if r["flagged"])
    total_h=sum(r["holders"] for r in reg_data)
    reg_rows=""
    for r in reg_data:
        fs=f"{r['float_shares']:,}" if r["float_shares"] else "N/A"
        fh=f'<span class="bdg bwarn">⚠ {r["flag_reason"]}</span>' if r["flagged"] else '<span class="bdg" style="background:rgba(52,211,153,.1);color:var(--vir-l);border-color:rgba(52,211,153,.2);">✓ Clean</span>'
        reg_rows+=f"<tr><td style='color:var(--text);font-weight:700;'>{r['ticker']}</td><td>{r['community_shares']:,}</td><td style='color:var(--text3);'>{fs}</td><td>{r['holders']}</td><td>{fh}</td></tr>"
    if not reg_rows: reg_rows="<tr><td colspan='5' style='color:var(--text3);text-align:center;padding:36px;'>No holdings registered yet. Add yours below to get started.</td></tr>"
    hr=""
    for i,h in enumerate(holdings):
        hr+=f"<tr><td style='color:var(--text);font-weight:700;'>{h['ticker']}</td><td>{h['shares']}</td><td>${h['buy_price']}</td><td><button class='btn bd' style='padding:3px 9px;font-size:11px;' onclick='rmH({i})'>Remove</button></td></tr>"
    if not hr: hr="<tr><td colspan='4' style='color:var(--text3);text-align:center;padding:18px;'>No holdings added yet.</td></tr>"
    market=get_market_bar()

    html=f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Vulcan — Registry</title>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>{CSS}</style></head>
<body>{sidebar("registry")}
<div class="main">
<div class="mbar">{mbar_html(market)}</div>
<div class="ph"><div class="pt">Public Share Registry</div><div class="ps">Community holdings · Cross-referenced against real float data · Fraud detection</div></div>
<div class="pb">
  <div style="background:rgba(99,102,241,.06);border:1px solid rgba(99,102,241,.15);border-radius:12px;padding:14px 18px;margin-bottom:20px;font-size:13px;color:var(--text2);line-height:1.7;" class="fi">
    ℹ️ <strong style="color:var(--text);">What is this?</strong> The Share Registry lets community members log their stock holdings.
    Vulcan cross-references these against Yahoo Finance float data to flag suspicious patterns — like a user claiming an unrealistically high percentage of a company's available shares.
    This creates a community-powered transparency layer without requiring broker access.
  </div>
  <div class="sg fi">
    <div class="sc"><div class="sl">Tracked Tickers</div><div class="sv neu">{len(reg_data)}</div></div>
    <div class="sc"><div class="sl">Flagged Entries</div><div class="sv {"down" if flagged>0 else "up"}">{flagged}</div><div class="ss">Suspicious activity</div></div>
    <div class="sc"><div class="sl">Total Holders</div><div class="sv neu">{total_h}</div></div>
  </div>
  <div class="card fi fi1" style="margin-bottom:20px;">
    <div class="ct">📝 Register a Holding</div>
    <p style="font-size:12px;color:var(--text3);margin-bottom:14px;">Voluntarily log your real stock holdings. Only share counts are public — your username and buy price are kept private.</p>
    <div style="display:grid;grid-template-columns:1fr 1fr 1fr auto;gap:10px;flex-wrap:wrap;">
      <div><label class="fl">Ticker</label><input type="text" id="ht" class="inp" placeholder="AAPL"></div>
      <div><label class="fl">Shares</label><input type="number" id="hs" class="inp" placeholder="10"></div>
      <div><label class="fl">Avg Buy Price</label><input type="number" id="hp" class="inp" placeholder="150.00"></div>
      <div style="display:flex;align-items:flex-end;"><button class="btn bg2" onclick="addH()">+ Register</button></div>
    </div>
  </div>
  <div class="card fi fi2" style="margin-bottom:20px;">
    <div class="ct">My Registered Holdings</div>
    <div class="tw"><table><thead><tr><th>Ticker</th><th>Shares</th><th>Buy Price</th><th>Action</th></tr></thead><tbody>{hr}</tbody></table></div>
  </div>
  <div class="card fi fi3">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;">
      <div class="ct" style="margin-bottom:0;">Community Registry</div>
      <button class="btn bo" onclick="location.reload()" style="font-size:11px;padding:6px 12px;">↻ Refresh</button>
    </div>
    <div class="tw"><table><thead><tr><th>Ticker</th><th>Community Shares</th><th>Real Float</th><th>Holders</th><th>Status</th></tr></thead><tbody>{reg_rows}</tbody></table></div>
    <div style="margin-top:14px;padding:13px;background:var(--surface2);border-radius:10px;font-size:11px;color:var(--text3);line-height:1.7;">
      🔍 <strong style="color:var(--text2);">Fraud detection logic:</strong> Entries are flagged when (1) community claims exceed 0.01% of a stock's real float — a statistically impossible level for a small app — or (2) multiple users report identical share counts, a common sign of fabricated data.
    </div>
  </div>
</div></div>
<script>
function addH(){{var t=document.getElementById('ht').value.trim().toUpperCase(),s=parseFloat(document.getElementById('hs').value),p=parseFloat(document.getElementById('hp').value);if(!t||!s||!p){{alert('Please fill all fields.');return;}}fetch('/add_holding',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{ticker:t,shares:s,buy_price:p}})}}).then(()=>location.reload());}}
function rmH(i){{fetch('/remove_holding',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{index:i}})}}).then(()=>location.reload());}}
</script></body></html>"""
    return html

@app.route("/alerts")
def alerts_view():
    if not logged_in(): return redirect(url_for("login"))
    try: triggered=check_alerts()
    except Exception as e:
        print(f"[vulcan] check_alerts error: {e}"); triggered=[]
    settings=load_settings()
    for a in triggered:
        try: send_alert_email(a,settings)
        except: pass
    try: alerts=load_alerts()
    except: alerts=[]
    ar=""
    for i,a in enumerate(alerts):
        dc="up" if a["direction"]=="above" else "down"
        ar+=f"<tr><td style='color:var(--text);font-weight:700;'>{a['ticker']}</td><td class='{dc}'>{a['direction'].capitalize()}</td><td style='font-family:\"JetBrains Mono\",monospace;'>${a['target']}</td><td><span class='bdg bwarn'>Active</span></td><td><button class='btn bd' style='padding:3px 9px;font-size:11px;' onclick='rmAlert({i})'>Remove</button></td></tr>"
    if not ar: ar="<tr><td colspan='5' style='color:var(--text3);text-align:center;padding:28px;'>No active alerts. Add one above.</td></tr>"
    trig_html="".join([f'<div style="background:rgba(52,211,153,.08);border:1px solid rgba(52,211,153,.25);border-radius:9px;padding:11px 14px;font-size:13px;color:var(--vir-l);margin-bottom:10px;">🔔 {a["ticker"]} hit ${a["current_price"]} (target: ${a["target"]} {a["direction"]})</div>' for a in triggered])
    market=get_market_bar()

    html=f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Vulcan — Alerts</title>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>{CSS}</style></head>
<body>{sidebar("alerts")}
<div class="main">
<div class="mbar">{mbar_html(market)}</div>
<div class="ph"><div class="pt">Price Alerts</div><div class="ps">Get notified when stocks hit your target price · Checks alerts on every page load</div></div>
<div class="pb">
  {trig_html}
  <div class="card fi" style="margin-bottom:20px;">
    <div class="ct">+ New Alert</div>
    <p style="font-size:12px;color:var(--text3);margin-bottom:14px;">Set a target price for any stock. When the condition is met on page load, you'll see a banner above and receive an email if configured.</p>
    <div style="display:grid;grid-template-columns:1fr 1fr 1fr auto;gap:10px;flex-wrap:wrap;">
      <div><label class="fl">Ticker</label><input type="text" id="at" class="inp" placeholder="AAPL"></div>
      <div><label class="fl">Target Price</label><input type="number" id="ap" class="inp" placeholder="200.00"></div>
      <div><label class="fl">Condition</label><select id="ad" class="inp"><option value="above">Rises above</option><option value="below">Falls below</option></select></div>
      <div style="display:flex;align-items:flex-end;"><button class="btn bp" onclick="addAlert()">+ Add Alert</button></div>
    </div>
  </div>
  <div class="card fi fi1" style="margin-bottom:20px;">
    <div class="ct">Active Alerts ({len(alerts)})</div>
    <div class="tw"><table><thead><tr><th>Ticker</th><th>Direction</th><th>Target</th><th>Status</th><th>Action</th></tr></thead><tbody>{ar}</tbody></table></div>
  </div>
  <div class="card fi fi2">
    <div class="ct">📧 Email Notifications</div>
    <p style="font-size:12px;color:var(--text3);margin-bottom:16px;line-height:1.7;">Connect Gmail to receive email alerts. Use a Gmail App Password (not your real password) — generate one at <span style="color:var(--indigo-l);">myaccount.google.com → Security → App Passwords</span>.</p>
    <div style="display:grid;grid-template-columns:1fr 1fr 1fr auto;gap:10px;flex-wrap:wrap;">
      <div><label class="fl">Your Email</label><input type="email" id="se" class="inp" value="{settings.get('email','')}"></div>
      <div><label class="fl">Gmail Sender</label><input type="email" id="sg" class="inp" value="{settings.get('gmail_user','')}"></div>
      <div><label class="fl">App Password</label><input type="password" id="sp" class="inp" placeholder="16-char code"></div>
      <div style="display:flex;align-items:flex-end;"><button class="btn bo" onclick="saveSettings()">Save</button></div>
    </div>
  </div>
</div></div>
<script>
function addAlert(){{var t=document.getElementById('at').value.trim().toUpperCase(),p=parseFloat(document.getElementById('ap').value),d=document.getElementById('ad').value;if(!t||!p)return;fetch('/add_alert',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{ticker:t,target:p,direction:d}})}}).then(()=>location.reload());}}
function rmAlert(i){{fetch('/remove_alert',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{index:i}})}}).then(()=>location.reload());}}
function saveSettings(){{fetch('/save_settings',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{email:document.getElementById('se').value,gmail_user:document.getElementById('sg').value,gmail_pass:document.getElementById('sp').value}})}}).then(r=>r.json()).then(()=>alert('Settings saved!'));}}
</script></body></html>"""
    return html


@app.route("/run")
def run():
    if not logged_in(): return jsonify({"error":"Unauthorized"}),401
    strat=request.args.get("strategy","balanced")
    run_bot(me(), strat)
    return jsonify({"status":"done"})

@app.route("/set_cash",methods=["POST"])
def set_cash():
    if not logged_in(): return jsonify({"error":"Unauthorized"}),401
    set_starting_cash(me(),float(request.json.get("amount",10000)))
    return jsonify({"status":"done"})

@app.route("/search")
def search():
    if not logged_in(): return jsonify({"error":"Unauthorized"}),401
    t=request.args.get("ticker","").upper()
    if not t: return jsonify({"error":"No ticker"})
    d=analyze_stock(t)
    return jsonify(d) if d else jsonify({"error":"Stock not found"})

@app.route("/recommend")
def recommend():
    if not logged_in(): return jsonify({"error":"Unauthorized"}),401
    # Use ALL confidence levels, not just High, so we always return results
    SCAN=["AAPL","MSFT","GOOGL","AMZN","TSLA","NVDA","META","SPY","QQQ","AMD","NFLX","DIS","BRK-B","JPM","BAC"]
    buys,sells=[],[]
    for t in SCAN:
        d=analyze_stock(t)
        if not d: continue
        # Include Medium and High signals
        if d["confidence"] in ("High","Medium"):
            (buys if d["prediction"]==1 else sells).append(d)
    # Sort: buys by lowest RSI (most oversold), sells by highest RSI (most overbought)
    buys.sort(key=lambda x:x["rsi"])
    sells.sort(key=lambda x:x["rsi"],reverse=True)
    return jsonify({"buys":buys[:6],"sells":sells[:4]})

@app.route("/chart")
def chart():
    if not logged_in(): return jsonify({"error":"Unauthorized"}),401
    t=request.args.get("ticker","").upper()
    p=request.args.get("period","6mo")
    if not t: return jsonify({"error":"No ticker"})
    return jsonify(get_chart_data(t,p))

@app.route("/add_stock",methods=["POST"])
def add_stock():
    if not logged_in(): return jsonify({"error":"Unauthorized"}),401
    t=request.json.get("ticker","").upper()
    wl=load_watchlist()
    if t and t not in wl: wl.append(t); save_watchlist(wl)
    return jsonify({"status":"added"})

@app.route("/remove_stock",methods=["POST"])
def remove_stock():
    if not logged_in(): return jsonify({"error":"Unauthorized"}),401
    t=request.json.get("ticker","").upper()
    wl=load_watchlist()
    if t in wl: wl.remove(t); save_watchlist(wl)
    return jsonify({"status":"removed"})

@app.route("/add_alert",methods=["POST"])
def add_alert():
    if not logged_in(): return jsonify({"error":"Unauthorized"}),401
    d=request.json
    alerts=load_alerts()
    alerts.append({"ticker":d.get("ticker","").upper(),"target":float(d.get("target",0)),"direction":d.get("direction","above")})
    save_alerts(alerts)
    return jsonify({"status":"added"})

@app.route("/remove_alert",methods=["POST"])
def remove_alert():
    if not logged_in(): return jsonify({"error":"Unauthorized"}),401
    i=request.json.get("index",-1)
    alerts=load_alerts()
    if 0<=i<len(alerts): alerts.pop(i); save_alerts(alerts)
    return jsonify({"status":"removed"})

@app.route("/save_settings",methods=["POST"])
def save_settings_route():
    if not logged_in(): return jsonify({"error":"Unauthorized"}),401
    save_settings(request.json)
    return jsonify({"status":"saved"})

@app.route("/add_holding",methods=["POST"])
def add_holding():
    if not logged_in(): return jsonify({"error":"Unauthorized"}),401
    d=request.json
    t=d.get("ticker","").upper()
    s=float(d.get("shares",0))
    bp=float(d.get("buy_price",0))
    if not t or not s or not bp: return jsonify({"error":"Missing data"})
    holdings=load_holdings()
    holdings.append({"ticker":t,"shares":s,"buy_price":bp})
    with open(HOLDINGS_FILE,"w",encoding="utf-8") as f: json.dump(holdings,f)
    update_registry(me(),t,s,bp,"add")
    return jsonify({"status":"added"})

@app.route("/remove_holding",methods=["POST"])
def remove_holding():
    if not logged_in(): return jsonify({"error":"Unauthorized"}),401
    i=request.json.get("index",-1)
    holdings=load_holdings()
    if 0<=i<len(holdings):
        t=holdings[i]["ticker"]; holdings.pop(i)
        with open(HOLDINGS_FILE,"w",encoding="utf-8") as f: json.dump(holdings,f)
        update_registry(me(),t,0,0,"remove")
    return jsonify({"status":"removed"})

if __name__=="__main__":
    app.run(debug=True,host="0.0.0.0")