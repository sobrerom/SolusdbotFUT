# SOLUSDBOT – Diagnostics Pack

## Contenuto
- `diagnostics.py` – verifica API/marketInfo/datafeeds e quantità (no ordini).
- `smoke_place.py` – ordini IOC reduceOnly di prova (per test firma/permessi).

## Uso locale
```bash
export PIONEX_API_KEY=...
export PIONEX_API_SECRET=...
python diagnostics.py > diag.json
python smoke_place.py > smoke.json
```

## Consigli
- Se `qty_calc.ok` è `false`, aumenta `grid.notional_per_side_usdt` o riduci `grid.levels`.
- Se `market_info.ok` è `false`, verifica `pionex.symbol` e permessi delle API.
