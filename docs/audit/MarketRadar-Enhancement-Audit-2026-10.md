# MarketRadar — Enhancement Audit & Phased Plan (2026-10-10)

Scope: the full repository at commit `3c4a575` on `main`. Every finding below
was read from source or reproduced; nothing is inferred from documentation
alone. It builds on, and does not repeat, the earlier
[Pre-Submission Audit](MarketRadar-Pre-Submission-Audit.md). Most of that
audit's blockers (SB-1 cache refresh, SB-2 Pulse location leakage, SB-3
validator, SB-4 location substitution, SB-5 Price Intelligence status codes,
R-7 trend keys) are fixed in the current code and covered by
`tests/test_audit_regressions.py`.

---

## 1. Architecture summary

```
React 19 + MUI 9 (8 lazy pages)  --axios-->  FastAPI (8 routers, /api/*)
                                                 |
          +--------------------------------------+-------------------------------+
          | spends credits                                      | read-only, free |
  Market Research  Competitors  Products  Price Intelligence    Trends  Pulse  Analyst
          |             |           |            |                 \      |      /
          +---- SerpApiOrganicService / SerpApiService / LivePriceService       |
                     |                                                          |
               ApiBudgetManager (cache 7d, usage rows)          observation tables
                     |                                                          |
             SerpApi: google, google_maps, google_shopping  ------>  SQLite (13 tables)
```

* **Engines integrated:** `google` (organic + local pack), `google_maps`
  (geocode + merchant discovery), `google_shopping`. Plus SerpApi's free
  `locations.json` (location resolution) and `account.json` (quota).
* **Persistence:** append-only observation tables, `competitor_observations`
  and `product_observations`, hang off one shared `merchants` identity table.
  Also `serp_searches`, `serp_search_results`, `serp_local_results`,
  `search_cache`, `api_usage`, and a legacy `market_observations`.
  `businesses`, `products`, `market_events` and `trend_observations` exist
  but nothing writes to them.
* **Schema management:** `create_all` plus an additive-column sync
  (`database/schema_sync.py`). No migration tool.
* **AI:** a vendor-neutral `AIProvider` protocol with an **empty registry**.
  Facts are computed by code, and an optional narrative is number- and
  claim-validated.

## 2. Implementation inventory

Status legend: **V** implemented and verified · **I** implemented but incomplete ·
**B** implemented but broken · **P** partially integrated · **U** UI-only or mock ·
**N** not implemented · **X** blocked by credentials or data.

| Module / feature | Status | Evidence | Gap |
|---|---|---|---|
| Market Research (`/api/serpapi/search`, `/recent`) | **I** | `routes/serpapi.py`, `MarketResearch.tsx` | No saved searches, no export, no related questions or clustering. Literal `hl=en`/`gl=us` in the transparency panel (`MarketResearch.tsx:419-423`). Reads non-existent `local_results.places` and `links.website` |
| Location resolution | **V** | `location_service.py`, conflict detection, tests | — |
| Search cache and usage rows | **B → fixed** | `api_budget.py` | Empty-result searches were treated as failures (see P0-2). No timeout. No retry. No pruning of expired rows |
| Competitor discovery | **V** | `competitor_service.py`, 4 test files | — |
| Competitor review (confirm/reject/edit) | **N** | no write endpoint for `merchants.status` | Required by spec §6 |
| Competitor monitoring / scheduled re-collection | **N** | — | |
| Product discovery and observations | **V** | `product_service.py` | Currency hard-coded `USD` (`product_service.py:314`). `$NN.NN`-only extraction (`merchant_website_provider.py:763-811`) |
| Cross-merchant product grouping and comparison | **N** | — | No GTIN/UPC/model use. Matching is token-based |
| Price Intelligence (`/api/prices/local`) | **I** | `live_price_service.py` | **Results are not persisted**, so they never feed Trends, Pulse or the Analyst. `currency="USD"`. Shopping price parsed by stripping `$` (`:317`) instead of using `extracted_price` |
| Legacy shopping prices (`/prices/search`, `/history`, `/changes`) | **P** | `routes/prices.py`, `intelligence_service.py` | No frontend caller. History matches the exact `product_name`. Provider failure gave a generic 500 (fixed) |
| Price change detection (increase/decrease/new/missing/outlier) | **N** | Only first-vs-last direction in `trends_service.py` | |
| Trends (observation-derived) | **V** | `trends_service.py` | No UI filters (`Trends.tsx:275-278` passes `{}`). No time window |
| Google Trends (search interest) | **N** | — | |
| Market Pulse | **V** | `pulse_service.py` | Trend values rendered raw (−1/0/1, no currency) at `MarketPulse.tsx:536-537` |
| AI Analyst — deterministic facts | **V** | `analyst_service.py` | Fixed analysis only. No free-form Q&A. Evidence chips are not inspectable |
| AI Analyst — narrative | **X/N** | `ai_provider.py:PROVIDER_REGISTRY = {}` | No adapter exists, so the narrative can never run |
| Opportunity scoring | **N** | — | |
| Reports and export (PDF/CSV/XLSX) | **N** | No export anywhere in the frontend or backend | |
| Saved research / research history | **I** | Only `serp_searches` (the last 5) | |
| Executive dashboard | **I** | `Dashboard.tsx` reads `/trends/summary` and `/serpapi/usage` | No filters, no recent changes, no failures or health panel. No fabricated KPIs ✅ |
| Usage tracking | **I** | `api_usage`, `account.json` | No per-feature view in the UI. **No configurable budget** — deliberately removed earlier ("spec 34") |
| Demo mode | **V** | `scripts/seed_demo_data.py` (`.example` domains, a separate DB file) | |
| Auth / rate limiting | **N** | — | Documented as local-only |
| Error boundary | **N → fixed** | — | |
| Frontend tests | **N** | no vitest/jest | |
| Backend tests | **V** | 525 passing at baseline | |

## 3. Confirmed bugs

| # | Severity | Location | Bug | Evidence |
|---|---|---|---|---|
| B-1 | P0 | `api_budget.py` (old line 559) | No request timeout. `GoogleSearch` defaults to **60000 s** | `venv/.../serp_api_client.py:35` |
| B-2 | P0 | `api_budget.py` (old line 561) | Any `error` key was treated as failure. SerpApi puts "Google hasn't returned any results for this query." in `error` on a **successful** empty search, so empty searches became 502s, and in Products a merchant catalogue with no hit became `provider_request_failed` | [SerpApi search errors](https://serpapi.com/search-errors), [status codes](https://serpapi.com/api-status-and-error-codes) |
| B-3 | P0 | `routes/prices.py:43-46`, `serpapi_service.py:45` | Provider failure on `/prices/search` returned a generic 500 | reproduced |
| B-4 | P0 | competitors/products/serpapi routes | `num`, `max_merchants` and `limit` were unbounded. `limit=-1` returned all rows | reproduced: `/api/products?limit=-1` → 200 |
| B-5 | P1 | `live_price_service.py:232`, `product_service.py:314` | Every price is labelled `USD`. Only `$NN.NN` is parsed | source |
| B-6 | P1 | `live_price_service.py:317` | Shopping price parsed with `str.replace("$")`. Ignores the provider's `extracted_price`. Fails on "1.234,56 €" and "₹1,200" | source |
| B-7 | P1 | `Competitors.tsx`, `Products.tsx` | A false "nothing saved yet" empty state shows while the saved list loads. `savedTotal` is stale after a search | frontend audit |
| B-8 | P1 | `Products.tsx:183-187` | A failed detail fetch does nothing silently | frontend audit |
| B-9 | P2 | `PriceIntelligence.tsx:207-248` | Literal `$`. `$---` rendering. A reference price of 0 is treated as missing | frontend audit |
| B-10 | P2 | `routes/serpapi.py` batch | Per-query failures are swallowed into a count with no reason | source |
| B-11 | P2 | `MarketResearch.tsx:83, 309` | Reads `local_results.places` and `links.website`, which the backend schema never returns (dead fallbacks, `any` types) | frontend audit |

## 4. Baseline (before any change, 2026-10-10)

| Command | Result |
|---|---|
| `backend: pytest -q` | **525 passed**, 1 deprecation warning (httpx `cgi`) |
| `frontend: npm run lint` (oxlint) | clean |
| `frontend: npm run build` | success. Largest chunks are `index` 343 kB and `trendApi` (recharts) 338 kB |
| Frontend tests | none exist |
| Free-endpoint smoke test (TestClient against a copy of the demo DB) | all read-only endpoints 200. Keyless search endpoints 503 |
| Live SerpApi calls | **not run**, to avoid spending credits. All provider behaviour is tested with mocks |

## 5. SerpApi engines — ranked by value

Checked against serpapi.com on 2026-10-10. Plans run from Free (250
searches/month, 50/hour) to Starter ($25, 1,000) and Developer ($75, 5,000).
"Cached, errored, and failed searches" are not counted
([pricing](https://serpapi.com/pricing)). Whether an *empty* successful
search is billed is not stated, so MarketRadar conservatively records it as 1
credit.

| Rank | Engine | Value to MarketRadar | Cost |
|---|---|---|---|
| 1 | `google_trends` | The only genuine *relative search-interest* signal, and the basis for "category growth", seasonality and geographic interest. `TIMESERIES` takes up to 5 comma-separated queries per request; `GEO_MAP_0` and `RELATED_QUERIES` take 1. `interest_over_time.timeline_data[].values[].extracted_value`. Interest is 0–100 relative, **not** volume or share | 1 per request, SerpApi-side cache is 1 h. Cache locally for 24 h |
| 2 | `google_news` | Evidence for "what changed in this market": dated, attributed sources (`news_results[].title/link/source.name/iso_date`). Use `iso_date`; `date` is a display string | 1 per request |
| 3 | `google_related_questions` / `google_autocomplete` | Cheap research expansion for Market Research (questions, keyword discovery) | 1 per request |
| 4 | `google_images` | Low analytical value. Only for product imagery | skip |
| 5 | `google_events` | Niche. Only some industries benefit | skip unless requested |

## 6. Phased plan

### P0 — correctness, reliability, security (**done in this pass**)
| Task | Files | Acceptance criteria | Status |
|---|---|---|---|
| Bounded request timeout (30 s) | `api_budget.py` | Every request sets `timeout ≤ 60` | ✅ tested |
| Retry transient failures with exponential backoff (2 retries); classify errors (auth / quota / invalid_request / transient / provider) and never retry permanent ones | `api_budget.py` | A timeout followed by success yields one usage row with success and 1 credit. A bad key gets 1 attempt and no sleep | ✅ tested |
| An empty successful search is a result, not a failure | `api_budget.py` | Market Research returns 200 `no_results` instead of 502. Empty responses are cached | ✅ tested |
| `/prices/search` provider failure → 502 | `serpapi_service.py`, `routes/prices.py` | 502 with the provider detail | ✅ tested |
| Bounds on `num` (1–100), `max_merchants` (1–10), `limit` (1–500) → 400 before any search | `routes/validation.py` + 3 routers | No `GoogleSearch` constructed on rejection | ✅ tested |
| Health reports DB status and whether keys are configured (never values) | `routes/health.py` | `database`, `serpapi_configured`, `ai_provider_configured` | ✅ tested |
| Frontend error boundary around pages, reset on navigation, reload on chunk failure | `components/ErrorBoundary`, `AppLayout.tsx` | A render error leaves the sidebar usable | ✅ build, lint and browser check |

### P1 — core feature completion
1. **Persist Price Intelligence observations** into `product_observations`
   (append-only, `source_type` preserved), so local prices feed
   Trends, Pulse and the Analyst. Done when a `/prices/local` run with mocked
   provider data creates rows, and `/trends/prices` shows them under the
   right merchant and location.
2. **Currency-correct prices.** Use `extracted_price` and `currency` from
   Shopping. Parse common currency symbols and decimal conventions in
   website snippets, and stop labelling everything USD. Done when tests
   cover `$`, `€`, `£`, `₹` and `1.234,56`, and an unknown symbol yields
   `currency=None` with price `unavailable`.
3. **Price change detection** over stored observations: increase, decrease,
   newly observed, no longer observed (worded as "not observed in latest
   run"), outlier (median ± k·MAD), conflicting merchant prices.
   Configurable thresholds. Requires ≥2 distinct measurements. Endpoint:
   `GET /api/prices/changes`, replacing the legacy single-pair version while
   keeping its shape.
4. **Competitor review**: `PATCH /api/competitors/{id}` with fields
   `review_status` (confirmed/rejected), name override and note, recorded as
   an audit row. The identity `status` is left unchanged. Done when a
   rejected competitor is excluded from Products merchant selection.
5. **Frontend fixes B-7, B-8, B-9, B-11**, plus Trends filters (market,
   location, query) wired to the existing API parameters.
6. **CSV export** for competitors, product observations, price observations
   and trend series, generated server-side from the same queries the UI uses.

### P2 — SerpApi integrations
1. `google_trends` provider and service: `trend_observations` gets a real
   writer. Interest over time (≤5 terms), interest by region, related
   queries, with 24 h cache. Trends UI tab "Search interest" with the
   relative-scale disclaimer.
2. `google_news` provider: `news_observations` (title, link, source,
   `iso_date`, query, collected_at). Market Research "News" tab, and an
   evidence source for the Analyst.
3. Related questions and autocomplete in Market Research.
4. Usage dashboard: per-engine and per-feature usage from `api_usage`, cost
   estimate from a configured plan price per search (source and date shown),
   and an **optional** monthly budget (off by default — see the decision
   below).

### P3 — AI and opportunity scoring
1. A real AI adapter, registered via `AI_PROVIDER`, keeping the existing
   validation. Then evidence-grounded Q&A: retrieve observation rows for the
   question, answer only from them, cite record IDs and URLs, and fall back
   to the deterministic analysis.
2. An explainable opportunity score:
   `score = 100 × (w_i·impact + w_c·confidence + w_f·freshness + w_r·relevance)`,
   with each input normalised to [0,1], weights configurable and summing to
   1, and a missing input contributing 0 and flagged. It is never presented
   as a probability. Opportunities are persisted with review status.

### P4 — polish and submission
PDF report (methodology, parameters, timestamps, sources, limitations).
Dashboard filters and a recent-changes panel. Vitest with Testing Library
for critical pages. README and API doc refresh. Screenshots. Remove unused
assets and CSS (`App.css`, `index.css`, `hero.png`, `react.svg`, `vite.svg`,
`marketApi.ts`, `types/price.ts`).

## 7. Decisions needed from the owner

1. **Usage budget.** An earlier design decision ("spec 34") removed any
   application-level credit budget in favour of SerpApi's own account quota.
   The new brief asks for a configurable budget. The proposal is an
   *opt-in* `SERPAPI_MONTHLY_BUDGET`, unset by default, which returns 429
   when exceeded.
2. **AI provider.** Which vendor and model to register. No adapter is shipped
   today, and none will be invented.
3. **Live verification.** Whether a small number of real searches (≈10–20
   credits) may be spent to verify the end-to-end flow after P1/P2. All
   automated tests use mocks.
