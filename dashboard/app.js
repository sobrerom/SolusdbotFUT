
const $ = (id)=>document.getElementById(id);
const pretty = (n, d=4)=> (n==null? "—" : (typeof n==="number"? n.toFixed(d): n));

async function loadJSON(path){
  try{
    const res = await fetch(path+`?t=${Date.now()}`);
    if(!res.ok) throw new Error(res.statusText);
    return await res.json();
  }catch(e){ return null; }
}

function setStatusBadge(status){
  const b = $("status-badge");
  b.classList.remove("ok","warn","panic");
  b.textContent = status || "—";
  if(status==="OK") b.classList.add("ok");
  else if(status==="WARN") b.classList.add("warn");
  else if(status==="PANIC"||status==="SUSPEND") b.classList.add("panic");
}

function fillOrders(tableBodyId, orders){
  const tb = $(tableBodyId);
  tb.innerHTML = "";
  if(!orders || !orders.length){
    tb.innerHTML = `<tr><td colspan="6" class="muted">Nessun dato</td></tr>`;
    return;
  }
  for(const o of orders){
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${o.ts_iso||"—"}</td><td>${o.side||"—"}</td><td>${pretty(o.price,4)}</td><td>${pretty(o.qty,4)}</td><td>${o.status||o.pnl||"—"}</td><td>${o.id||"—"}</td>`;
    tb.appendChild(tr);
  }
}

async function refresh(){
  $("year").textContent = new Date().getFullYear();
  const state  = await loadJSON("../state.json") || {};
  const orders = await loadJSON("../orders.json") || { open:[], closed:[], stats:{} };
  const cfg    = await loadJSON("../config.json") || null;

  setStatusBadge(state.status);
  $("m-ts").textContent = state.ts_iso || "—";
  $("m-mid").textContent = pretty(state.mid,4);
  $("m-vol").textContent = (state.vol_pct!=null? state.vol_pct.toFixed(3)+"%" : "—");
  $("m-div").textContent = (state.div_bps!=null? state.div_bps.toFixed(1)+" bps" : "—");
  $("m-lev").textContent = (state.lev!=null? state.lev.toFixed(2)+"x" : "—");
  $("m-grid").textContent = (state.grid? `[${pretty(state.grid[0],4)} .. ${pretty(state.grid[1],4)}] @ L=${state.grid[2]}`:"—");
  $("m-alpha").textContent = (state.indicators?.alpha_signal || "—");
  $("m-tf").textContent = (state.indicators?.tf || "—");

  if(cfg){
    $("kv-target").textContent = (cfg.pid?.target_vol_pct!=null? cfg.pid.target_vol_pct+"%" : "—");
    $("kv-pid").textContent = cfg.pid? `(${cfg.pid.kp}, ${cfg.pid.ki}, ${cfg.pid.kd})`:"—";
    $("kv-safe").textContent = (cfg.safe_mode? `warn=${cfg.safe_mode.vol_warn_pct}%, panic=${cfg.safe_mode.vol_panic_pct}%`:"—");
    $("kv-loop").textContent = (cfg.daemon? `${cfg.daemon.loop_seconds}s / backoff<=${cfg.daemon.exponential_backoff_max_s}s`:"—");
  }else{
    $("kv-target").textContent = "—"; $("kv-pid").textContent = "—"; $("kv-safe").textContent = "—"; $("kv-loop").textContent = "—";
  }
  $("kv-ind").textContent = (state.indicators? JSON.stringify(state.indicators): "—");

  fillOrders("open-orders-body", orders.open);
  fillOrders("closed-orders-body", orders.closed);
  $("s-pnl-day").textContent   = (orders.stats?.pnl_day!=null? pretty(orders.stats.pnl_day,3)+" USDT":"—");
  $("s-trades-day").textContent= (orders.stats?.trades_day!=null? orders.stats.trades_day:"—");
  $("s-win-7d").textContent    = (orders.stats?.win_7d!=null? (orders.stats.win_7d*100).toFixed(1)+"%":"—");
  $("s-sharpe-30d").textContent= (orders.stats?.sharpe_30d!=null? orders.stats.sharpe_30d.toFixed(2):"—");
}

$("refresh-btn").addEventListener("click", refresh);
refresh();
