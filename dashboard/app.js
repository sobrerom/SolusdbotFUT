const $=(id)=>document.getElementById(id);
const pretty=(n,d=4)=> (n==null || isNaN(n) ? "—" : Number(n).toFixed(d));
async function loadJSON(path){
  try{
    const r = await fetch(path + `?t=${Date.now()}`);
    if(!r.ok) throw new Error(r.statusText);
    return await r.json();
  }catch(e){ return null; }
}

function setStatusBadge(status){
  const b = $("status-badge");
  b.classList.remove("ok","warn","panic");
  if(status==="WARN") b.classList.add("warn");
  else if(status==="PANIC"||status==="SUSPEND") b.classList.add("panic");
  else b.classList.add("ok");
  b.textContent = status||"OK";
}

function fillOrders(id, arr){
  const tb=$(id);
  tb.innerHTML="";
  if(!arr || !arr.length){
    const tr=document.createElement("tr");
    tr.innerHTML=`<td colspan="7">—</td>`;
    tb.appendChild(tr);
    return;
  }
  for(const o of arr.slice(0,100)){
    const tr=document.createElement("tr");
    tr.innerHTML=`<td>${o.ts_iso||"—"}</td><td>${o.side||"—"}</td><td>${o.qty||"—"}</td><td>${pretty(o.px,4)}</td><td>${o.venue||"—"}</td><td>${o.status||o.pnl||"—"}</td><td>${o.id||"—"}</td>`;
    tb.appendChild(tr);
  }
}

// Minimal line chart without external libs
function plotLine(canvas, data){
  const ctx=canvas.getContext("2d");
  const W=canvas.width = canvas.clientWidth;
  const H=canvas.height = canvas.height; // keep height attribute
  ctx.clearRect(0,0,W,H);
  if(!data || data.length<2){ return; }
  const xs = data.map(d=>d.t);
  const ys = data.map(d=>d.v);
  const minY = Math.min(...ys), maxY = Math.max(...ys);
  const pad = 8;
  const scaleX = (x)=> pad + (x - xs[0])/(xs[xs.length-1]-xs[0]+1e-9) * (W-2*pad);
  const scaleY = (y)=> H - pad - (y - minY)/(maxY-minY+1e-9) * (H-2*pad);
  ctx.lineWidth=2;
  ctx.beginPath();
  ctx.moveTo(scaleX(xs[0]), scaleY(ys[0]));
  for(let i=1;i<xs.length;i++){
    ctx.lineTo(scaleX(xs[i]), scaleY(ys[i]));
  }
  ctx.strokeStyle = "#3de77d";
  ctx.stroke();
}

function parseTs(s){
  const t = (typeof s==="number") ? s : Date.parse(s || 0);
  return isFinite(t) ? t : 0;
}


// -------- Optional WebSocket Live Updates --------
let WS = null, wsConnected = false, wsBackoff = 1000, wsTimer = null;
let latestState = null, latestOrders = null, latestConfig = null, latestReport = null;
let pollingTimer = null;
const WS_FORCE_OFF = new URLSearchParams(location.search).get("ws")==="off";

function setLiveStatus(mode){ // "WS","POLL","OFF"
  const dot = $("live-dot"), txt = $("live-text");
  dot.classList.remove("on","off","warn","panic");
  if(mode==="WS"){ dot.classList.add("on"); txt.textContent = "LIVE"; }
  else if(mode==="POLL"){ dot.classList.add("off"); txt.textContent = "POLL"; }
  else { dot.classList.add("off"); txt.textContent = "OFF"; }
}

function stopPolling(){
  if(pollingTimer){ clearInterval(pollingTimer); pollingTimer = null; }
}
function startPolling(fn){
  stopPolling();
  pollingTimer = setInterval(fn, 5000);
}

function wsURLFromConfig(cfg){
  try{
    return cfg && cfg.dashboard && cfg.dashboard.ws_url ? cfg.dashboard.ws_url : (window.WS_URL || null);
  }catch(_){ return null; }
}

function connectWS(url){
  if(!url || WS_FORCE_OFF){ setLiveStatus("POLL"); return; }
  try{
    WS = new WebSocket(url);
  }catch(e){
    setLiveStatus("POLL");
    return;
  }
  WS.onopen = ()=>{
    wsConnected = true;
    wsBackoff = 1000;
    setLiveStatus("WS");
    stopPolling();
    // Optional hello
    try{ WS.send(JSON.stringify({type:"hello", client:"dashboard", ts:Date.now()})); }catch(_){}
  };
  WS.onclose = ()=>{
    wsConnected = false;
    setLiveStatus("POLL");
    // resume polling
    if(!pollingTimer) startPolling(()=>refresh(currentRange));
    // reconnect with backoff
    clearTimeout(wsTimer);
    wsTimer = setTimeout(()=>connectWS(url), Math.min(wsBackoff, 15000));
    wsBackoff *= 2;
  };
  WS.onerror = ()=>{
    // will trigger close; switch to poll
    setLiveStatus("POLL");
  };
  WS.onmessage = (ev)=>{
    try{
      const msg = JSON.parse(ev.data);
      // Accept either full or delta payloads
      if(msg.state) latestState = Object.assign({}, latestState||{}, msg.state);
      if(msg.orders) latestOrders = Object.assign({}, latestOrders||{}, msg.orders);
      if(msg.report) latestReport = Object.assign({}, latestReport||{}, msg.report);
      if(msg.config) latestConfig = Object.assign({}, latestConfig||{}, msg.config);
      // Render immediately using in-memory caches
      render(latestState, latestOrders, latestConfig, latestReport, currentRange);
    }catch(_){}
  };
}

async function refresh(range=100){
  $("year").textContent = new Date().getFullYear();

  const s = await loadJSON("../state.json") || {};
  const o = await loadJSON("../orders.json") || {open:[],closed:[],stats:{}};
  const c = await loadJSON("../config.json") || null;
  const r = await loadJSON("../report.json") || null;

  latestState = s; latestOrders = o; latestConfig = c; latestReport = r;
  render(s,o,c,r,range);

  // Status + hero (handled in render)
  setStatusBadge(s.status);
  $("hero-equity").textContent = (s.equity_usdt!=null) ? `${Number(s.equity_usdt).toFixed(2)} USDT` : "—";
  $("hero-cap").textContent    = (s.cap_usdt!=null) ? `${Number(s.cap_usdt).toFixed(2)} USDT` : "—";
  $("hero-lev").textContent    = (s.leverage!=null) ? `${Number(s.leverage).toFixed(2)}x` : "—";
  $("hero-state").textContent  = s.status || "—";

  // Metrics
  $("m-ts").textContent = s.ts_iso || "—";
  $("m-mid").textContent = pretty(s.mid,4);
  $("m-vol").textContent = s.realized_vol != null ? pretty(s.realized_vol*100,2)+"%" : "—";
  $("m-div").textContent = s.cross_div_bps != null ? pretty(s.cross_div_bps,1)+" bps" : "—";
  $("m-lev").textContent = s.leverage != null ? pretty(s.leverage,2)+"x" : "—";
  $("m-grid").textContent = (s.grid_lo!=null && s.grid_hi!=null) ? `[${pretty(s.grid_lo,4)} .. ${pretty(s.grid_hi,4)}] @ L=${s.grid_levels||"—"}` : "—";
  $("m-alpha").textContent = s.alpha_sig != null ? pretty(s.alpha_sig,3) : "—";
  $("m-tf").textContent = s.timeframe || "—";
  $("m-mode").textContent = s.mode || "—";

  // Orders
  fillOrders("open-orders", (o.open||[]));
  fillOrders("closed-orders", (o.closed||[]));

  // Chart data from report.json or state history fallback
  let series=[];
  if(r && (r.mid_series || r.series)){
    const src = r.mid_series || r.series;
    const sub = src.slice(-range);
    series = sub.map(d=>({t: parseTs(d.t||d.ts||d.time||d[0]), v: Number(d.mid||d.v||d[1])})).filter(x=>isFinite(x.v));
  }else if(s && Array.isArray(s.mid_hist)){
    const sub = s.mid_hist.slice(-range);
    series = sub.map((v,i)=>({t: i, v: Number(v)}));
  }
  plotLine(document.getElementById("mid-chart"), series);

  // Stale detection (>120s)
  const now = Date.now();
  const ts = parseTs(s.ts_epoch_ms || s.ts_ms || s.ts || s.ts_iso);
  const isStale = ts ? (now - ts > 120000) : true;
  const banner = document.getElementById("stale-banner");
  if(isStale) banner.classList.remove("hidden"); else banner.classList.add("hidden");
}

let currentRange = 100;
function setup(){
  // Try to fetch config first, then decide whether to open WS
  loadJSON("../config.json").then(cfg=>{
    latestConfig = cfg;
    const url = wsURLFromConfig(cfg);
    if(!WS_FORCE_OFF && url){ try{ connectWS(url); }catch(_){ setLiveStatus("POLL"); } }
    if(!wsConnected){ setLiveStatus(url ? "POLL" : "OFF"); }
  }).catch(()=>{ setLiveStatus("OFF"); });

  document.querySelectorAll(".chip[data-range]").forEach(btn=>{
    btn.addEventListener("click",()=>{
      currentRange = Number(btn.getAttribute("data-range"))||100;
      document.querySelectorAll(".chip[data-range]").forEach(b=>b.classList.remove("active"));
      btn.classList.add("active");
      refresh(currentRange);
    });
  });
  document.getElementById("refresh").addEventListener("click",()=>refresh(currentRange));
  refresh(currentRange);
  startPolling(()=>refresh(currentRange));
}
document.addEventListener("DOMContentLoaded", setup);


function render(s,o,c,r,range){
  // Status + hero
  setStatusBadge(s.status);
  $("hero-equity").textContent = (s && s.equity_usdt!=null) ? `${Number(s.equity_usdt).toFixed(2)} USDT` : "—";
  $("hero-cap").textContent    = (s && s.cap_usdt!=null) ? `${Number(s.cap_usdt).toFixed(2)} USDT` : "—";
  $("hero-lev").textContent    = (s && s.leverage!=null) ? `${Number(s.leverage).toFixed(2)}x` : "—";
  $("hero-state").textContent  = s && s.status ? s.status : "—";

  // Metrics
  $("m-ts").textContent = (s && s.ts_iso) || "—";
  $("m-mid").textContent = pretty(s && s.mid,4);
  $("m-vol").textContent = (s && s.realized_vol != null) ? pretty(s.realized_vol*100,2)+"%" : "—";
  $("m-div").textContent = (s && s.cross_div_bps != null) ? pretty(s.cross_div_bps,1)+" bps" : "—";
  $("m-lev").textContent = (s && s.leverage != null) ? pretty(s.leverage,2)+"x" : "—";
  $("m-grid").textContent = (s && s.grid_lo!=null && s.grid_hi!=null) ? `[${pretty(s.grid_lo,4)} .. ${pretty(s.grid_hi,4)}] @ L=${s.grid_levels||"—"}` : "—";
  $("m-alpha").textContent = (s && s.alpha_sig != null) ? pretty(s.alpha_sig,3) : "—";
  $("m-tf").textContent = (s && s.timeframe) || "—";
  $("m-mode").textContent = (s && s.mode) || "—";

  // Orders
  fillOrders("open-orders", (o && o.open) || []);
  fillOrders("closed-orders", (o && o.closed) || []);

  // Chart data
  let series=[];
  if(r && (r.mid_series || r.series)){
    const src = r.mid_series || r.series;
    const sub = src.slice(-range);
    series = sub.map(d=>({t: parseTs(d.t||d.ts||d.time||d[0]), v: Number(d.mid||d.v||d[1])})).filter(x=>isFinite(x.v));
  }else if(s && Array.isArray(s.mid_hist)){
    const sub = s.mid_hist.slice(-range);
    series = sub.map((v,i)=>({t: i, v: Number(v)}));
  }
  plotLine(document.getElementById("mid-chart"), series);

  // Stale detection (>120s)
  const now = Date.now();
  const ts = parseTs(s && (s.ts_epoch_ms || s.ts_ms || s.ts || s.ts_iso));
  const isStale = ts ? (now - ts > 120000) : true;
  const banner = document.getElementById("stale-banner");
  if(isStale) banner.classList.remove("hidden"); else banner.classList.add("hidden");
}
