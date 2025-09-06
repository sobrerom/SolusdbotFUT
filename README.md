# SOLUSDBOT — Alpha Breakout Grid (Live, Pages-ready)

- Breakout con SL/TP + Grid dinamica
- WS fills + fallback REST
- Hysteresis, timeframe auto (1m/5m), leva PID, cap 3%
- Dashboard HTML con auto-refresh (15s)
- Workflow con timeout 7m e deploy GitHub Pages

## Setup rapido
1. Repo pubblico → Settings → Pages → **Source = GitHub Actions**
2. Secrets: `PIONEX_API_KEY`, `PIONEX_API_SECRET`
3. Actions → Run workflow (**SOLUSDBOT Live**)
Dashboard: `https://<owner>.github.io/<repo>/dashboard/`
