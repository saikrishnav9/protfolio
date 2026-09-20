# Pulse

A **$0** data + AI portfolio: live public signals land in a lakehouse, **tests block the LLM**, and recruiters get a GitHub Pages URL that always has Gold data.

This is not a chatbot. The model is a warehouse job. If Bronze/Silver contracts fail, inference does not run and the cost stays `$0.00`.

## Recruiter demo

After you push to `main` and enable **GitHub Pages → Source: GitHub Actions**, paste the **portfolio** URL:

`https://<you>.github.io/<repo>/`

Pulse (the live project) is:

`https://<you>.github.io/<repo>/pulse/`

Walkthrough (about a minute):

1. Portfolio lands on your name and the featured Pulse card.
2. **Open live demo** — KPI row shows last run, Gold count, tests, enricher, cost.
3. Map markers are **Gold table rows**, not a vector index.
4. Click a canned question — the SQL is on the page. Nothing in the browser can `DROP` or `UPDATE`.
5. Toggle **Replay quality-gate failure**. Tests go red, the LLM step is marked skipped, cost stays `$0`.

Suggested note to send with the link:

> Portfolio: https://&lt;you&gt;.github.io/&lt;repo&gt;/  
> Featured project Pulse: live NWS + EONET events land in DuckDB; contracts must pass before an LLM writes Gold. Open /pulse/ and toggle “Replay quality-gate failure”.

## Architecture

```text
NOAA NWS + NASA EONET + Open-Meteo     (free, no key)
        │
        ▼
GitHub Actions every 6 hours           (free on a public repo)
  ingest → quality gate → enrich
  if tests fail → skip LLM, keep last Gold
        │
        ▼
Parquet on GitHub Pages
        │
        ▼
This dashboard (DuckDB-WASM in the browser)
```

| Plane | What it does |
|---|---|
| Data | Bronze raw JSON/Parquet, Silver typed events, Gold structured labels |
| Control | GitHub Actions + Python/dbt contracts. Failed tests skip enrich |
| Decision | Groq / Gemini / GitHub Models write JSON; heuristic fallback if no key or bad JSON |

AI never runs in the recruiter’s browser. There is no API key on the public page.

## Stack (all free)

- Python 3.11+, DuckDB, dbt-duckdb, Pydantic, httpx
- GitHub Actions (orchestrator) + GitHub Pages (URL)
- Groq or Gemini optional; otherwise rules-based enrich (`cost_usd = 0`)
- DuckDB-WASM + Leaflet for the demo

No AWS/GCP bill, no Streamlit sleep, no always-on Airflow.

## Run locally

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
python -m pulse pipeline --offline
python -m pulse serve
```

Open http://127.0.0.1:8080 for the portfolio and http://127.0.0.1:8080/pulse/ for Pulse.

Edit `site/profile.js` (GitHub, LinkedIn, email) and add more work in `site/projects.js`. Pulse is already the featured init project.

- `--offline` uses committed fixtures (also what CI uses on pull requests).
- Omit `--offline` to hit live NOAA / EONET / Open-Meteo. If they fail, fixtures are used so the demo never goes empty.
- `--no-dbt` runs the Python contracts only (faster). The default path also runs dbt models and tests.

Optional `.env`:

```
GROQ_API_KEY=...
# or GEMINI_API_KEY=...
```

Without a key, Gold is still built with the heuristic enricher. With a key, the first 80 rows are sent as structured JSON; malformed output falls back to rules.

## What recruiters should notice

- Live (or live-shaped) ingest, not a single CSV
- Idempotent event ids, typed severity, coordinates
- A real quality gate: null `event` / `alert_id` **blocks** inference
- Structured LLM output validated by Pydantic
- Token counts and `$0` cost on the dashboard
- Read-only SQL in the browser against Parquet
- Tests in CI; Pages deploy only from a successful pipeline

## Layout

```text
site/            recruiter portfolio (GitHub Pages root)
dashboard/       Pulse live demo (copied to site/pulse on assemble)
pulse/           ingest, enrich, quality gate, CLI
dbt/             bronze / silver / gold models
fixtures/        offline + chaos payloads
.github/workflows/pulse.yml
```

## GitHub setup (once)

1. Push this repo (public, so Actions minutes stay free).
2. Repo **Settings → Pages → Build and deployment → GitHub Actions**.
3. Optional: add `GROQ_API_KEY` or `GEMINI_API_KEY` in Actions secrets.
4. Run the **pulse** workflow (or wait for the 6-hour cron).
5. Paste the Pages URL.

Pull requests run pytest + an offline pipeline and do not deploy.

## Design choices

- **Actions instead of hosted Airflow** — the SLA is hours; a free always-on scheduler would need a credit card.
- **Parquet + DuckDB-WASM instead of a warehouse account** — Gold is a file. The browser is a read replica.
- **Canned SQL instead of open NL→SQL** — a public LLM box with a warehouse is how demos get abused.
- **Heuristic fallback** — quota expiry must not blank the recruiter URL.
