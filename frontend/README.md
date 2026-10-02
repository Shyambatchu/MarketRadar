# MarketRadar Frontend

React + TypeScript + Vite + MUI client for MarketRadar.

## Setup

```bash
cd frontend
npm install
cp .env.example .env        # optional; defaults to http://127.0.0.1:8001/api
```

## Run

```bash
npm run dev
```

Served at <http://localhost:5173> (Vite picks 5174 if 5173 is taken; both are
allowed by the backend's CORS configuration).

The backend must be running on port **8001**.

## Build and lint

```bash
npm run build      # tsc -b && vite build
npm run lint       # oxlint
npm run preview    # serve the production build
```

`npm run build` type-checks with `tsconfig.app.json`, which enables
`noUnusedLocals`. It is therefore stricter than a bare `tsc --noEmit` — use
`npm run build` as the real gate before shipping.

## Layout

```
frontend/src/
├── main.tsx                entry point
├── App.tsx                 routes
├── layouts/AppLayout.tsx   sidebar shell + backend status
├── pages/                  one directory per module
├── components/             shared presentational components
├── services/               axios client and per-module API wrappers
├── types/                  API response types
└── theme/                  MUI theme
```

## Modules

| Route | Page | State |
|---|---|---|
| `/` | Dashboard | entry cards for every module |
| `/research` | Market Research | implemented (organic + local search) |
| `/competitors` | Competitors | implemented (discovery, evidence, saved list) |
| `/products` | Products | implemented (catalogue evidence, product vs price status) |
| `/prices` | Price Intelligence | implemented (nearby stores, verified prices) |
| `/trends` | Trends | implemented (read-only series) |
| `/pulse` | Market Pulse | implemented (read-only snapshot) |
| `/analyst` | AI Analyst | implemented (deterministic analysis; narrative needs a provider adapter) |
| `*` | Not found | fallback for unknown paths |

## UI conventions

- Never present a failed request as an empty result. `/api/prices/local`
  returns `stages[]`; a stage with `status: "error"` renders as a warning, not
  as `0`.
- Never display a number that is not backed by real data. Use an explicit
  empty state instead.
- Distinguish "not found in available sources" from "not sold". The former is
  what the evidence supports.
- Catalogue evidence is labelled as such and must not imply confirmed stock at
  a physical store.
- Only the newest request may render. `PriceIntelligence` tracks a request id
  so a slow earlier response cannot overwrite a newer one.
