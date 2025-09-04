# CI fix per path
Questo workflow cerca automaticamente `selftest.py` e `main.py` in qualsiasi cartella del repo, così non fallisce se la directory non è `SOLUSDBOT-main/`.

Se vuoi mantenere la struttura proposta in precedenza, assicurati che il codice sia in `SOLUSDBOT-main/` e che esistano:
- `SOLUSDBOT-main/selftest.py`
- `SOLUSDBOT-main/main.py`
