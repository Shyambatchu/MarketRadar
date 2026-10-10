# MarketRadar

**"Turn live market signals into smarter business decisions."**

MarketRadar is an industry-agnostic market-intelligence platform for new and
growing businesses. Given a **market**, a **location** and optionally a
**product**, it discovers the competing businesses, checks what they offer and
at what verified price, tracks how those signals change over time, and
summarises the result as evidence-referenced facts.

It is built around one rule: **report what was observed and how strongly it is
evidenced — never invent a conclusion.** "Price unavailable" is not "product
unavailable", "not in the latest search" is not "closed", and one reading seen
twice is not a trend.

| Document | PDF | Purpose |
|---|---|---|
| [Project Document](docs/MarketRadar-Project-Document.md) | [PDF](docs/MarketRadar-Project-Document.pdf) | Full project document: problem, design, architecture, modules, data, API, testing, limitations |
| [Demo Video Guide](docs/MarketRadar-Demo-Video-Guide.md) | [PDF](docs/MarketRadar-Demo-Video-Guide.pdf) | Step-by-step script for the submission video, and which test data to use |
| [API Reference](docs/API.md) | — | Every endpoint, its parameters, status codes and whether it spends credits |
| [Enhancement Audit & Plan](docs/audit/MarketRadar-Enhancement-Audit-2026-10.md) | — | October 2026 audit, implementation inventory and phased plan |
| [Pre-Submission Audit](docs/audit/MarketRadar-Pre-Submission-Audit.md) | [PDF](docs/audit/MarketRadar-Pre-Submission-Audit.pdf) | Audit findings, submission blockers and the fix log |
| [Module Working & Execution Flow](docs/audit/MarketRadar-Module-Working-and-Execution-Flow.md) | [PDF](docs/audit/MarketRadar-Module-Working-and-Execution-Flow.pdf) | Per-module execution flow with sequence diagrams |
| [Technical Documentation](docs/MarketRadar-Technical-Documentation.md) | [PDF](docs/MarketRadar-Technical-Documentation.pdf) | Earlier long-form technical reference (the audit fix log records later changes) |
| This README | [PDF](docs/MarketRadar-README.pdf) | Setup and run steps |

---

## 1. Modules

| Module | Page | Main endpoint(s) | Spends SerpApi credits? |
|---|---|---|---|
| Dashboard | `/` | `GET /api/dashboard` | **No** — counts, recent price changes, top opportunities, freshness, health |
| Opportunities | `/opportunities` | `/api/opportunities`, `POST /refresh`, `PATCH /{id}` | **No** — ranked, explainable leads from stored evidence |
| Market Research | `/research` | `GET /api/serpapi/search` | Yes, 1 per uncached search (related questions included free) |
| Market Signals | `/signals` | `/api/signals/search-interest*`, `/api/signals/news` | Yes, 1 per uncached Google Trends / Google News request |
| Competitors | `/competitors` | `/api/competitors/search`, `PATCH /api/competitors/{id}` (review) | Search: 1 per uncached search. Review: no |
| Trends | `/trends` | `GET /api/trends/*` | **No** |
| Market Pulse | `/pulse` | `GET /api/market-pulse` | **No** |
| Price Intelligence | `/prices` | `GET /api/prices/local`, `GET /api/prices/alerts` | Local search: ~3 + one per nearby merchant with a website. Price changes: no |
| Products | `/products` | `GET /api/products/search` | Yes, 1 + up to `max_merchants` (default 5, max 10) |
| AI Analyst | `/analyst` | `GET /api/analyst/analysis`, `POST /api/analyst/ask` | **No** |
| Reports | `/reports` | `/api/reports`, `/api/saved-searches` | **No** — print-ready HTML, save as PDF |
| Usage & Cost | `/usage` | `GET /api/serpapi/usage/breakdown` | **No** |

Every list can be exported as CSV (`/api/export/*.csv`). Full endpoint list:
[docs/API.md](docs/API.md).

Search responses are cached (7 days for search, 24 h for Google Trends, 6 h for
news), so repeating an identical search costs nothing. Location lookup uses
SerpApi's free location catalogue. An optional `SERPAPI_MONTHLY_BUDGET` refuses
live searches beyond a monthly cap (HTTP 429) while still serving cached results.

## 2. Technology

- **Frontend:** React 19, TypeScript, Vite 8, Material UI 9, React Router 7, Recharts, Axios; Vitest + Testing Library
- **Backend:** Python 3.12, FastAPI 0.115, Pydantic 2, SQLAlchemy 2
- **Database:** SQLite (`backend/data/market_radar.db`, created automatically; additive schema sync)
- **Market data (SerpApi):** Google Search (organic, local pack, related questions), Google Maps,
  Google Shopping, Google Trends, Google News
- **AI:** a vendor-neutral `AIProvider` interface with a bundled Anthropic (Claude) adapter
  (`AI_PROVIDER=anthropic`). Facts are computed by code; a model only narrates or answers
  from numbered evidence, and its output is validated (no new figures, no forecasts, every
  fact cited) before display. Without a provider the analyst runs deterministically.

---

## 3. Prerequisites

| Tool | Version | Check with |
|---|---|---|
| Python | **3.12** (tested on 3.12.3) | `python --version` |
| Node.js | **20.19+ or 22.12+** (tested on 24.18) — required by Vite 8 | `node --version` |
| npm | 10+ (tested on 11.16) | `npm --version` |
| SerpApi key | optional — needed only for the live search modules (Research, Signals, Competitors, Products, Price Intelligence) | <https://serpapi.com/manage-api-key> |

Without a SerpApi key, the app still runs. The search modules then return
"SerpApi key not configured" (HTTP 503), and Trends, Market Pulse and the AI
Analyst work on whatever history the database holds — or on the demo data
from step 6.

## 4. Run the project — exact steps

Open **two terminals**, one for the backend and one for the frontend. All
commands start from the project root (the folder containing this README).

### 4.1 Backend (terminal 1)

**Windows (PowerShell)**

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt -r requirements-dev.txt
Copy-Item .env.example .env
notepad .env        # set SERPAPI_API_KEY=<your key>, save, close
uvicorn app.main:app --reload --port 8001
```

If PowerShell blocks `Activate.ps1`, run
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, or use
`.\venv\Scripts\activate.bat` from `cmd`.

**macOS / Linux**

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env
nano .env           # set SERPAPI_API_KEY=<your key>
uvicorn app.main:app --reload --port 8001
```

Check it: open <http://localhost:8001/api/health>. It should show
`"status":"ok"`, `"database":"ok"` and whether the SerpApi key and an AI
provider are configured (never their values). Interactive API docs are at
<http://localhost:8001/docs>.

The first start creates `backend/data/market_radar.db` and its tables. It
never drops or overwrites existing data.

### 4.2 Frontend (terminal 2)

**Windows (PowerShell)**

```powershell
cd frontend
npm install
Copy-Item .env.example .env
npm run dev
```

**macOS / Linux**

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

Open <http://localhost:5173>. The sidebar footer shows **Backend Connected**
when the API is reachable. Copying `.env` is optional: the frontend defaults to
`http://127.0.0.1:8001/api`.

### 4.3 Every later run

Start the backend with **one** of the two commands below, then the frontend.
Run each from the project root.

**Terminal 1, option A: demo data** (no API key, no credits; recommended for
a first look, because the Trends charts have real movements to show):

```powershell
cd backend; .\venv\Scripts\Activate.ps1; $env:DATABASE_URL="sqlite:///./data/demo_market_radar.db"; uvicorn app.main:app --reload --port 8001
```

Create the demo database once beforehand with
`python scripts\seed_demo_data.py` (see 6.2).

**Terminal 1, option B: your real data**

```powershell
cd backend; .\venv\Scripts\Activate.ps1; Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue; uvicorn app.main:app --reload --port 8001
```

**Terminal 2: frontend**

```powershell
cd frontend; npm run dev
```

Open <http://localhost:5173>. `$env:DATABASE_URL` lasts only for that
terminal window, so closing it returns you to the real database.

macOS / Linux:

```bash
# terminal 1, demo data
cd backend && source venv/bin/activate && DATABASE_URL=sqlite:///./data/demo_market_radar.db uvicorn app.main:app --reload --port 8001
# terminal 1, real data
cd backend && source venv/bin/activate && uvicorn app.main:app --reload --port 8001
# terminal 2
cd frontend && npm run dev
```

### 4.4 Guided tour (5 minutes, demo data)

With the backend on demo data (option A above), this walk-through shows every
read-only module without spending a credit.

1. **Dashboard (`/`).** Live figures from the database: businesses tracked,
   markets observed, product observations and verified prices. A bar chart
   shows observations per market, split by Competitors and Products. The
   **Search credits** panel shows credits spent, searches answered from the
   7-day cache (credits saved) and the SerpApi plan usage. A compact version
   of that meter sits in the sidebar on every page.
2. **Trends (`/trends`), Prices tab.** *Measured movements* charts the series
   that actually changed: House Blend Coffee Beans at Sample Bean Co.,
   $14.99 → $15.99 (+6.67%). In the table, each row has a sparkline; click a
   row to open its full chart. The Example Roasters row was read twice at the
   same price, so it is drawn grey as *insufficient history*: one reading seen
   twice is not a trend.
3. **Trends, Visibility tab.** Search positions swap between the two
   searches. The position axis is reversed, so higher on the chart always
   means a better position, and colour follows meaning (green = better).
4. **Trends, Merchant presence tab.** A business missing from the latest
   search is flagged *not in latest*, never *closed*.
5. **Market Pulse (`/pulse`).** Choose Coffee Shops in Sample City (demo
   data) for a one-page snapshot of that market.
6. **AI Analyst (`/analyst`).** Same context. Every statement is computed
   from data and cites its evidence; nothing is invented.
7. **Bike Repair** (in Pulse or Analyst). It has only one search, so every
   series correctly reports *insufficient history*.

With a SerpApi key and real data (option B), use the inputs in 6.3 for
Competitors, Products, Price Intelligence and Market Research.

## 5. Run the tests

```bash
cd backend
# activate the venv first (see 4.1)
pytest
```

Expected result: **653 passed**. The tests:

- run against a throwaway database (`tests/_test_market_radar.db`) that
  `tests/conftest.py` creates and deletes. They refuse to run if pointed at the
  real database.
- never call SerpApi or an AI provider: every response is a scripted stub, so the
  suite spends no credits and needs no API key or network.

Frontend:

```bash
cd frontend
npm test           # Vitest + Testing Library (22 tests, all API calls mocked)
npm run lint       # oxlint
npm run build      # TypeScript type-check (tsc -b) + production build
```

## 6. Test data

There are three kinds of test data. Use the right one for the job.

### 6.1 Automated test data (backend unit/integration tests)

This data lives inside the test files (`backend/tests/*.py`) and
`tests/stubs.py`. It uses fictional businesses on reserved `.example` domains
and scripted SerpApi payloads. `pytest` builds it and deletes it on every run,
so there is nothing to set up.

### 6.2 Demo data (no API key, no credits)

This is synthetic history for showing Trends, Market Pulse and the AI Analyst
end to end. It is written to a **separate** database file and never touches
`market_radar.db`.

```powershell
cd backend
.\venv\Scripts\Activate.ps1
python scripts\seed_demo_data.py              # creates data\demo_market_radar.db
$env:DATABASE_URL="sqlite:///./data/demo_market_radar.db"
uvicorn app.main:app --reload --port 8001
```

```bash
# macOS / Linux
python scripts/seed_demo_data.py
DATABASE_URL=sqlite:///./data/demo_market_radar.db uvicorn app.main:app --reload --port 8001
```

It contains two contexts, both at location **"Sample City (demo data)"**:

| Context | What it demonstrates |
|---|---|
| **Coffee Shops** (two searches, 10 days apart) | Real trend directions: price 14.99 → 15.99; search positions swap; rating 4.5 → 4.6. A business absent from the latest search is flagged "not in latest" (not "closed"). A product found but with no verifiable price. A price read twice unchanged stays "insufficient history". Price statistics from 3 distinct prices. |
| **Bike Repair** (one search) | Every series is "insufficient history" — one measurement is never a trend |

- Rebuild the demo file with `python scripts/seed_demo_data.py --reset`.
- To return to real data, close the terminal (or run
  `Remove-Item Env:DATABASE_URL` in PowerShell / `unset DATABASE_URL` in bash)
  and start the backend normally.

### 6.3 Live search inputs (uses SerpApi credits)

These inputs produce good results on the live provider:

| Page | Market / Product | Location | Notes |
|---|---|---|---|
| Competitors | `Wine Retail` | `Holmdel, NJ` | Local + organic results, rejected directories shown |
| Competitors | `Coffee Shops` | `Austin, Texas` | |
| Products | product `Kendall Jackson Vintner's Reserve Chardonnay 750ml`, market `Wine Retail` | `Holmdel, NJ` | Shows found / verified price / unknown side by side |
| Price Intelligence | `Cycling Frog 5mg Grapefruit 12oz 6pk`, radius 25 | `08807` | Nearby-store funnel |
| Market Research | `Wine stores` | `Holmdel, NJ` | |

These inputs show validation and cost nothing (rejected before any search):

| Input | Result |
|---|---|
| Competitors with no location | "A location is required…" |
| Location `asdfqwerzx` | "could not be matched to a supported search location" |
| Location `Holmdel, Germany` | Refused: "'Germany' does not match the closest supported location" |
| Market `x` | "too short to describe a market" |

## 7. Configuration

`backend/.env` (template: `backend/.env.example`; a blank value means "not set"):

| Variable | Default | Purpose |
|---|---|---|
| `SERPAPI_API_KEY` | — | SerpApi key, needed for the live search modules |
| `DATABASE_URL` | `sqlite:///./data/market_radar.db` | database location (relative to `backend/`) |
| `CORS_ORIGINS` | localhost/127.0.0.1 on 5173 and 5174 | origins allowed to call the API |
| `AI_PROVIDER`, `AI_API_KEY`, `AI_MODEL` | empty | `anthropic` + an Anthropic API key enables narrative summaries and written Q&A answers. `AI_MODEL` defaults to `claude-opus-5-5` |
| `SERPAPI_MONTHLY_BUDGET` | empty (no cap) | optional cap on live searches per calendar month |
| `SERPAPI_PLAN_MONTHLY_PRICE_USD`, `SERPAPI_PLAN_SEARCHES_PER_MONTH` | empty | cost-estimate inputs. When empty, the plan reported by SerpApi is priced from the published table (source and date shown in the UI) |
| `PRICE_CHANGE_MIN_PERCENT`, `PRICE_OUTLIER_MAD_K`, `PRICE_OUTLIER_MIN_MERCHANTS`, `PRICE_DISPERSION_MIN_PERCENT` | 5, 3.5, 4, 25 | price-change detection thresholds |
| `OPPORTUNITY_WEIGHT_*`, `OPPORTUNITY_FRESHNESS_HALF_LIFE_DAYS` | 0.40/0.30/0.15/0.15, 14 | opportunity score weights (normalised) and freshness half-life |

`frontend/.env` (template: `frontend/.env.example`):

| Variable | Default | Purpose |
|---|---|---|
| `VITE_API_BASE_URL` | `http://127.0.0.1:8001/api` | backend address |

## 8. Project structure

```
MarketRadar/
├── backend/
│   ├── app/
│   │   ├── main.py            FastAPI app, CORS, table creation
│   │   ├── config.py          settings from .env
│   │   ├── routes/            HTTP endpoints (thin: validation → service → status code)
│   │   ├── services/          business logic (discovery, identity, trends, pulse, analyst)
│   │   ├── providers/         merchant-website evidence provider
│   │   ├── models/            SQLAlchemy tables
│   │   ├── schemas/           Pydantic request/response models
│   │   └── database/          engine, session, additive column sync
│   ├── scripts/seed_demo_data.py
│   ├── tests/                 pytest suite (isolated DB, no live calls)
│   └── data/                  SQLite database (git-ignored)
├── frontend/
│   └── src/
│       ├── pages/             one folder per module
│       ├── services/          API client per module
│       ├── types/             TypeScript response types
│       ├── components/  layouts/  theme/
└── docs/                      project document, demo guide, audit
```

## 9. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Sidebar shows **Backend Unavailable** | Backend not running on port 8001, or `VITE_API_BASE_URL` points elsewhere |
| Search returns **"SerpApi key not configured"** (503) | Set `SERPAPI_API_KEY` in `backend/.env` and restart the backend |
| **"could not be matched to a supported search location"** (422) | Use a city, a postal code, or "City, Full State Name" (e.g. `Holmdel, New Jersey`) |
| **"The search provider did not respond"** (502) | SerpApi error or quota exhausted — check the SerpApi dashboard |
| Trends say **"insufficient history"** everywhere | Expected until the same search is repeated **after** the 7-day cache expires. Use the demo data (6.2) to see directions |
| Market Pulse / AI Analyst list is empty | No observations yet — run a Competitors or Products search, or use the demo data |
| `npm run dev` fails with a Node version error | Upgrade Node to 20.19+ / 22.12+ |
| Port 5173 in use | Vite moves to 5174 automatically; the backend allows both |
| `Activate.ps1 cannot be loaded` | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |

## 10. Known limitations

- **No authentication.** Run locally only: the search endpoints spend SerpApi credits.
  Request bounds (`num` ≤ 100, `max_merchants` ≤ 10, list `limit` ≤ 500) and the optional
  monthly budget limit cost exposure, but are not access control.
- **PDF export** is the browser's "Save as PDF" on the print-ready report page; no PDF
  library is bundled.
- **Prices** are parsed from symbols and ISO codes in several currencies; a bare "$" is
  resolved from the market's country (US, CA, AU, ...) and left unknown elsewhere. A price
  without an established currency is never verified. Figures in different currencies are
  never averaged or compared.
- **Product matching** is token-based (with size/unit and variant checks). It does not use
  GTIN/UPC, which the indexed sources rarely expose.
- **Organic search results** carry no geography. An out-of-area business found only that
  way is recorded as `discovered` with "location not verified" — and can be rejected in review.
- **Google Trends** values are relative interest within one request, never volume or share.
- **Opportunity scores** rank leads for review; they are not validated against outcomes.
- **Change detection** needs two distinct measurements; within the cache window a repeated
  search is the same measurement.
- **SQLite with additive schema sync**, not a migration tool. Adequate for a single-user
  install; PostgreSQL + Alembic is the path for multi-user deployment.

## 11. Database safety

The application database is `backend/data/market_radar.db`. It holds cached
SerpApi responses (paid for) and usage history.

- Tests never touch it.
- The demo seeder refuses to write to it.
- The app only ever adds tables and columns; it never drops them.

Back the file up before experimenting.

## 12. Packaging for submission

Include the source, `docs/`, both `.env.example` files and this README.
**Exclude**:

- `backend/.env` (contains your real API key)
- `backend/venv/`
- `frontend/node_modules/`
- `frontend/dist/`
- `backend/data/*.db`
- `_quarantine/`
- `__pycache__/`
- `.pytest_cache/`

The reviewer recreates the database and environments by following section 4.

## 13. Roadmap

- Authentication, per-user workspaces and rate limiting before any non-local deployment.
- PostgreSQL with managed migrations (Alembic).
- Scheduled re-collection (competitor monitoring) so history builds without manual searches.
- GTIN/UPC-based product identity where a source exposes it.
- Server-side PDF rendering if a pixel-exact PDF is required.
