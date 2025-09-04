# SOLUSDBOT – Fixed scaffolding (0409)

Questa versione include:
- Correzioni minime ai file Python per renderli eseguibili (stub sicuri).
- `requirements.txt`, `.env.example`, `config.example.yaml`.
- Workflow GitHub Actions schedulato (`.github/workflows/solusdbot-cron.yml`).
- Persistenza di stato (`SOLUSDBOT-main/state.json`) per ultimi parametri e prezzi.
- Trend filter (SMA) che adatta il numero di livelli della griglia.

## Uso locale
```bash
cp .env.example .env
cp config.example.yaml config.yaml
pip install -r requirements.txt
python SOLUSDBOT-main/selftest.py
python -m SOLUSDBOT-main.main   # oppure: python SOLUSDBOT-main/main.py
```

## Secrets (CI)
- Imposta in GitHub → Settings → Secrets → Actions:
  - `PIONEX_API_KEY`
  - `PIONEX_API_SECRET`
  - `DASHBOARD_TOKEN`
