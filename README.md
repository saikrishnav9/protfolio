# Sai Krishna Vasireddy

Portfolio for a data engineer. The featured project is **Pulse** — a live briefing desk for weather and earth events.

This repository is meant to stay **public**. GitHub Pages on a free account only serves a public site from a public repo, and public Actions minutes stay free. There are no API keys in the pages you can open in a browser.

## Live site

| Page | URL |
| --- | --- |
| Portfolio | https://saikrishnav9.github.io/protfolio/ |
| Pulse | https://saikrishnav9.github.io/protfolio/pulse/ |

If those 404, turn the repo **public**, then **Settings → Pages → Build and deployment → Source: GitHub Actions**, and re-run the **pulse** workflow.

## Pulse in one minute

Pulse is not a chatbot. Public feeds land as warehouse tables. Contracts must pass before any label is written. The map and briefing cards read Gold, not a prompt.

1. Open `/pulse/`.
2. Click **Play the landing** — one warning walks Ingest → Bronze → contracts → Silver → Enrich → Gold.
3. **Play it again** lands the next signal and stamps **Refreshed**.
4. Read the briefing. Toggle **Show the SQL** if you want the warehouse question.

Sources: NOAA NWS, NASA EONET, Open-Meteo. If a live pull fails, committed fixtures keep the desk from going blank.

```text
NWS + EONET + Open-Meteo
        │
        ▼
GitHub Actions (every 6 hours)
  ingest → tests → enrich → Gold
  failed tests skip the model
        │
        ▼
GitHub Pages  (site/ + site/pulse/)
```

## Publish (once)

1. Keep the repository **Public** (required for a free public Pages URL).
2. **Settings → Pages → Source: GitHub Actions**.
3. Optional: add `GROQ_API_KEY` or `GEMINI_API_KEY` as Actions secrets. Without a key, Gold is still built with rules.
4. Push to `master` (or `main`). The **pulse** workflow tests, runs the lakehouse, and deploys `site/`.

Pull requests run tests and an offline pipeline. They do not deploy.

No keys are shipped to the public site. Secrets stay in Actions.

## Run locally

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS / Linux: source .venv/bin/activate
pip install -e ".[dev]"
python -m pulse pipeline --offline
python -m pulse serve
```

- Portfolio: http://127.0.0.1:8080
- Pulse: http://127.0.0.1:8080/pulse/

`--offline` uses fixtures (same path as pull requests). Omit it to hit live APIs. `--no-dbt` runs the Python contracts only.

## Layout

```text
site/                 Pages root — portfolio
dashboard/            Pulse UI (copied to site/pulse)
pulse/                ingest, tests, enrich, CLI
dbt/                  bronze / silver / gold
fixtures/             offline payloads
.github/workflows/    test → pipeline → Pages
```

## License

MIT. See [LICENSE](LICENSE).
