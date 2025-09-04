SOLUSDBOT – Recenter & Auto‑Optimize (rev A)

Questo progetto implementa un grid bot manuale per la coppia SOL/USDT su Pionex tramite le API ufficiali. A differenza dei bot proprietari, usa ordini limite nativi (supportati e sicuri) e integra logiche avanzate di ri‑centraggio e gestione.

Struttura del progetto

pionex_api.py → client minimale per le API Pionex (pubbliche e private, con firma HMAC SHA‑256).

main.py → logica di trading: trend filter, ATR‑based adaptive grid, recenter automatico, cleanup ordini.

config.yaml → configurazione di parametri e risk management.

selftest.py → esecuzione locale in modalità dry‑run.

.github/workflows/cron.yml → workflow GitHub Actions per avvio automatico (ogni 10 minuti o manuale).

Setup

1. Requisiti

Python 3.11+

Librerie: requests, pyyaml

Account GitHub (per usare Actions) e account Pionex con API key/secret.

2. Configurazione

Inserisci le chiavi API Pionex come secrets nel repo:

PIONEX_API_KEY

PIONEX_API_SECRET

Modifica config.yaml secondo le tue preferenze:

invest_usdt: capitale da destinare al bot.

grids: numero di livelli di griglia.

lower_pct/upper_pct: ampiezza del box.

trend_filter: per sospendere in trend forte.

atr_*: per adattare l’ampiezza alla volatilità.

3. Esecuzione locale

export PIONEX_API_KEY="tuachiave"
export PIONEX_API_SECRET="tuasegreta"
export DRY_RUN=true  # true per test, false per ordini reali
python selftest.py

4. Esecuzione automatica (GitHub Actions)

Il workflow .github/workflows/cron.yml:

gira ogni 10 minuti (cron: "*/10 * * * *"),

può essere lanciato manualmente da Actions > Run workflow,

usa concurrency per garantire un solo run attivo e cancella quello precedente.

Funzionalità principali

Single instance → nessuna duplicazione di workflow.

Recenter automatico → se il prezzo esce dal box oltre la soglia (recenter_when_outside_by_pct).

Trend filter → mette in pausa il bot se |SMA50 − SMA200|/prezzo > soglia.

Adaptive grid (ATR) → box più largo nei momenti di alta volatilità.

Seed base → acquisto iniziale per poter subito vendere.

Rispetto dei minimi → quantità e notional minimi da common/symbols.

Limiti

Le API Pionex non espongono endpoint per creare/chiudere i grid bot proprietari: per questo il progetto usa ordini limite manuali.

I bilanci disponibili tramite API non includono i fondi bloccati dentro i bot Pionex già attivi.

Consigli operativi

Testa sempre in DRY_RUN=true prima di andare live.

Tieni d’occhio le fee (0,05% maker/taker su spot): impattano la redditività della griglia.

Puoi espandere il progetto con:

notifiche Telegram/Discord,

skew dinamico del box,

tracking PnL con log ordini eseguiti.
