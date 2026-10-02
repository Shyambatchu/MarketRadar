# MarketRadar Backend

FastAPI service for MarketRadar. Generic, industry-agnostic market
intelligence: no merchant, product, industry or location is special-cased in
production logic.

## Setup

```bash
cd backend
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env           # then set SERPAPI_API_KEY
```

## Run

```bash
uvicorn app.main:app --reload --port 8001
```

Health check: <http://127.0.0.1:8001/api/health> → `{"status":"ok","service":"market-radar-api"}`

Interactive API docs: <http://127.0.0.1:8001/docs>

## Test

```bash
pytest
```

`pytest.ini` restricts collection to `tests/`, and `tests/conftest.py` forces
`DATABASE_URL` at an isolated test database before any `app.*` module is
imported. See **Database safety** below — this is not optional.

## Layout

```
backend/
├── app/
│   ├── main.py                     app assembly, CORS, router registration
│   ├── config.py                   pydantic-settings, reads .env
│   ├── database/                   engine, session, declarative Base
│   ├── models/                     SQLAlchemy models
│   ├── schemas/                    Pydantic request/response models
│   ├── routes/                     HTTP layer
│   ├── services/                   business logic
│   └── providers/                  external evidence sources
├── tests/
├── data/                           application database lives here
├── requirements.txt
├── requirements-dev.txt
└── pytest.ini
```

## Database safety

The application database is `backend/data/market_radar.db`. It holds cached
SerpApi responses (paid credits) and API usage history.

Test fixtures call `Base.metadata.drop_all(bind=engine)`. The engine is built
at import time from `DATABASE_URL`, so if that resolves to the application
database, **running the test suite destroys it**. This has happened.

Two guards are in place and must stay:

1. `tests/conftest.py` sets `DATABASE_URL` to an isolated test database before
   any `app.*` import. An environment variable takes precedence over `.env`.
2. A session-scoped fixture asserts `_test_` appears in the engine URL and
   aborts the run otherwise.

Before changing anything about test configuration, verify:

```bash
python -c "from app.config import settings; print(settings.DATABASE_URL)"
```

## API

Implemented:

| Method | Path | Notes |
|---|---|---|
| GET | `/api/health` | liveness |
| GET | `/api/prices/local` | Price Intelligence funnel: merchant discovery → product evidence → price evidence. 400 bad input/radius, 422 unresolvable area, 502 provider failure, 503 no key. |
| GET | `/api/serpapi/search` | Google organic + local results |
| POST | `/api/serpapi/search/batch` | batched organic search (max 20) |
| GET | `/api/serpapi/usage` | observed provider usage; no artificial budget |
| GET | `/api/serpapi/recent` | recent stored searches |
| GET | `/api/competitors/search` | competitor discovery (persists merchants + observations) |
| GET | `/api/competitors`, `/api/competitors/{id}` | saved competitors (DB only) |
| GET | `/api/products/search` | product evidence across a market's merchants (persists observations) |
| GET | `/api/products`, `/api/products/{id}` | saved product observations (DB only) |
| GET | `/api/trends/summary`, `/prices`, `/availability`, `/visibility`, `/merchants` | read-only trend series; filter by `market` and `location` |
| GET | `/api/market-pulse/options`, `/api/market-pulse` | read-only snapshot of one market + location |
| GET | `/api/analyst/analysis` | deterministic evidence-referenced analysis (+ validated summary when a provider is registered) |

Status codes for search endpoints: 400 unusable request, 422 location with no
provider-supported equivalent, 429 rate limited, 502 provider failed,
503 SerpApi key not configured.

Legacy, not used by the frontend: `/api/prices/search`, `/api/prices/history`,
`/api/prices/changes` (Google Shopping observations), and the stub
`/api/market/search`.

## Design rules

- **Three separate stages.** Merchant discovered ≠ product available ≠ price
  available ≠ price verified. Each nearby merchant carries an independent
  `product_status` and `price_status`.
- **Evidence scope.** `evidence_scope` distinguishes a merchant *catalogue*
  listing from confirmed *store inventory*. Catalogue evidence never claims
  stock at a physical address.
- **Provenance.** A result is attributed to a merchant domain only when it is
  actually served by that domain. A `site:` query that finds nothing falls
  back to open-web results, which are not merchant evidence.
- **Discovery broad, verification strict.** Product identity comes from the
  title and URL path, never from a result snippet, which describes a page
  rather than a product.
- **Statistics.** Only `price_status == "verified"` observations enter
  lowest/average/highest.
- **Failed stage ≠ zero.** Every response carries `stages[]`; a provider that
  errored reports `status: "error"`, never `0` results.
- **No artificial API budgets.** Caching and execution de-duplication remain;
  daily/per-search limits were removed deliberately and must not return.
- **No mock data in `app/`.** Fixtures belong in `tests/`.
