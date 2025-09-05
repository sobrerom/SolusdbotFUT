# SOLUSDBOT — Alpha Breakout Grid (Live Ready)

**Obiettivo:** ~6 operazioni/giorno su SOLUSDT futures, impiego max **3%** del portafoglio, **leva dinamica** via PID in funzione del target **1%/die** e della volatilità.  
**Tutele:** 3 fonti dati (min 1 attiva), autosospensioni su divergenza/vol/quorum, daemon con backoff e SIGTERM, dashboard HTML.

## Novità in questo bundle
- **Pionex REST wrapper implementato** (configurabile da `config.yaml`: base_url, headers, paths).  
- **Timeframe candele automatico**: switch 1m/5m in base a regime (volatilità, stato feed, progresso verso 6 trade/die).  
- **Risk cap 3%** completato: sizing su equity USDT reale (se disponibile) o su fallback.  

> Verifica gli endpoint REST e gli header richiesti dal tuo account Pionex; se differiscono, aggiorna i campi in `config.yaml` senza toccare il codice.

## Struttura
```
.
├─ main.py                         # loop daemon, Alpha + PID, risk cap, timeframe auto
├─ alpha.py                        # breakout box w/ strong close
├─ datafeeds.py                    # mids + OHLC 1m/5m (Binance→Bybit→OKX)
├─ grid.py, pid.py, filters.py, util.py, report.py
├─ pionex_api.py                   # REST pronto con replace grid / orders / fills / equity
├─ config.yaml, requirements.txt
├─ dashboard/ (index.html, styles.css, app.js)
└─ .github/workflows/
   ├─ solusdbot-live.yml
   └─ cleanup-old-runs.yml
```

## Setup rapido
1. Aggiungi i **segreti** del repo: `PIONEX_API_KEY`, `PIONEX_API_SECRET`.
2. Se necessario, personalizza `config.yaml` → `pionex.base_url`, `pionex.endpoints.*`, header.
3. Avvia **SOLUSDBOT Live** da GitHub Actions (o attendi la schedule).

## Timeframe automatico
- 1m se mercato è calmo e stai sotto il target di trade giornalieri.
- 5m in condizioni WARN/PANIC o se la volatilità realizzata supera ~1.5%.
- Hysteresis: mantiene l’ultimo timeframe a parità di condizioni.

## Sizing & Rischio
- **Cap**: max `risk.max_portfolio_pct` del portafoglio (default 3%).  
- **Leverage PID**: maggiore con vol < target; minore con vol > target.  
- **Throttling**: 6 trade/die con `cooloff_seconds` ~15m tra segnali stessa direzione.

## Dashboard
Apri `dashboard/index.html` (locale o GitHub Pages). Mostra **Alpha Signal** e **Timeframe** usato, oltre a metriche/ordini/stat.

## Note
- Gli endpoint REST Pionex possono variare: la classe accetta percorsi e headers da config.  
- Se il tuo account Pionex usa un formato JSON diverso, adatta le chiavi nel wrapper (sezione parse).

Buon trading e test prudente! 🚀
