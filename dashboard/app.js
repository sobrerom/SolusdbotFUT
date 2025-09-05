const $=(id)=>document.getElementById(id);
const pretty=(n,d=4)=>(n==null?"—":(typeof n==="number"?n.toFixed(d):n));

async function loadJSON(p){try{const r=await fetch(p+`?t=${Date.now()}`);if(!r.ok)throw new Error(r.statusText);return await r.json()}catch(e){return null}}

function setStatusBadge(s){const b=$("status-badge");b.classList.remove("ok","warn","panic");b.textContent=s||"—";if(s==="OK")b.classList.add("ok");else if(s==="WARN")b.classList.add("warn");else if(s==="PANIC"||s==="SUSPEND")b.classList.add("panic")}

function fillOrders(id,arr){const tb=$(id);tb.innerHTML="";if(!arr||!arr.length){tb.innerHTML=`<tr><td colspan="6" class="muted">Nessun dato</td></tr>`;return}for(const o of arr){const tr=document.createElement("tr");tr.innerHTML=`<td>${o.ts_iso||"—"}</td><td>${o.side||"—"}</td><td>${pretty(o.price,4)}</td><td>${pretty(o.qty,4)}</td><td>${o.status||o.pnl||"—"}</td><td>${o.id||"—"}</td>`;tb.appendChild(tr)}}

async function refresh(){
  $("year").textContent = new Date().getFullYear();
  const s=await loadJSON("../state.json")||{},o=await loadJSON("../orders.json")||{open:[],closed:[],stats:{}},c=await loadJSON("../config.json")||null;
  setStatusBadge(s.status);
  $("m-ts").textContent=s.ts_iso||"—";
  $("m-mid").textContent=pretty(s.mid,4);
  $("m-vol").textContent=(s.vol_pct!=null?s.vol_pct.toFixed(3)+"%":"—");
  $("m-div").textContent=(s.div_bps!=null?s.div_bps.toFixed(1)+" bps":"—");
  $("m-lev").textContent=(s.lev!=null?s.lev.toFixed(2)+"x":"—");
  $("m-grid").textContent=(s.grid?`[${pretty(s.grid[0],4)} .. ${pretty(s.grid[1],4)}] @ L=${s.grid[2]}`:"—");
  $("m-alpha").textContent=(s.indicators?.alpha_signal||"—");
  $("m-tf").textContent=(s.indicators?.tf||"—");
  $("m-mode").textContent=(s.indicators?.mode||"—");

  if(c){
    $("kv-target").textContent=(c.pid?.target_vol_pct!=null?c.pid.target_vol_pct+"%":"—");
    $("kv-pid").textContent=c.pid?`(${c.pid.kp}, ${c.pid.ki}, ${c.pid.kd})`:"—";
    $("kv-safe").textContent=(c.safe_mode?`warn=${c.safe_mode.vol_warn_pct}%, panic=${c.safe_mode.vol_panic_pct}%`:"—");
    $("kv-loop").textContent=(c.daemon?`${c.daemon.loop_seconds}s / backoff<=${c.daemon.exponential_backoff_max_s}s`:"—");
  }else{$("kv-target").textContent="—";$("kv-pid").textContent="—";$("kv-safe").textContent="—";$("kv-loop").textContent="—"}
  $("kv-ind").textContent=(s.indicators?JSON.stringify(s.indicators):"—");

  fillOrders("open-orders-body",o.open);
  fillOrders("closed-orders-body",o.closed);
  $("s-pnl-day").textContent=(o.stats?.pnl_day!=null?pretty(o.stats.pnl_day,3)+" USDT":"—");
  $("s-trades-day").textContent=(o.stats?.trades_day!=null?o.stats.trades_day:"—");
  $("s-win-7d").textContent=(o.stats?.win_7d!=null?(o.stats.win_7d*100).toFixed(1)+"%":"—");
  $("s-sharpe-30d").textContent=(o.stats?.sharpe_30d!=null?o.stats.sharpe_30d.toFixed(2):"—");
}

$("refresh-btn").addEventListener("click",refresh);
refresh();
setInterval(refresh, 15000);
