# SOLUSDBOT – Pacchetto aggiornamenti
- Import robusti, default di config e gestione `grid` mancante
- Persistenza stato (crea `SOLUSDBOT-main/state.json` a runtime)
- Workflow con `entrypoint` e `PYTHONPATH` già impostati

## Locale
cp .env.example .env
cp config.example.yaml config.yaml   # oppure usa config.futures.example.yaml
pip install -r requirements.txt
python SOLUSDBOT-main/selftest.py
python SOLUSDBOT-main/main.py

## GitHub Actions
- Settings → Secrets → Actions: `PIONEX_API_KEY`, `PIONEX_API_SECRET`, `DASHBOARD_TOKEN`
- Actions → *SOLUSDBOT cron (robust import)* → Run workflow
- (facoltativo) imposta `entrypoint`: es. `SOLUSDBOT-main/main.py`
