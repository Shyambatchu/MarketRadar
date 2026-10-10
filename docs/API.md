# MarketRadar API reference

Base URL: `http://localhost:8001/api`. The interactive OpenAPI docs at
`http://localhost:8001/docs` are generated from the same code and are always current.

**Credits.** Endpoints marked 💳 can make a live SerpApi request: one search credit per
uncached request, and a cached response costs nothing. Every other endpoint reads the
database only and is free.

**Status codes used consistently:**

| Code | Meaning |
|---|---|
| 400 | The request is unusable (missing or invalid parameter, out-of-range bound). Nothing was searched. |
| 404 | The record does not exist. |
| 422 | The location has no provider-supported equivalent. It is never reported as "no results". |
| 429 | The optional monthly search budget (`SERPAPI_MONTHLY_BUDGET`) is used up. Nothing was spent. |
| 502 | The provider failed. This is never the same as a search that found nothing (that is a 200 with an empty list). |
| 503 | A required key (`SERPAPI_API_KEY`) is not configured. |

## System

| Method | Path | Notes |
|---|---|---|
| GET | `/health` | `status`, `database`, `serpapi_configured`, `ai_provider_configured`. Never returns key values. |
| GET | `/dashboard?market&location&days` | Counts, freshness, recent price changes, top opportunities, recent reports and searches, health. |

## Search and discovery 💳

| Method | Path | Notes |
|---|---|---|
| GET | `/serpapi/search?q&location&num(1–100)&hl&gl&google_domain` | Organic and local results, plus `related_questions` and `related_searches` from the same response. |
| POST | `/serpapi/search/batch` | `{queries: [≤20], location?}`. Failures are reported per query in `errors`. |
| GET | `/serpapi/recent` | Last searches. Free. |
| GET | `/serpapi/usage` | Local usage plus SerpApi account quota (free account endpoint). |
| GET | `/serpapi/usage/breakdown` | Usage per engine and feature, monthly credits against the budget, and a cost estimate with its basis. Free. |
| GET | `/competitors/search?market&q&location&num` | Discovers businesses from local and organic results. Persists observations. |
| GET | `/competitors?market&location&status&review_status&limit(1–500)` | Saved competitors. Free. |
| GET | `/competitors/{id}` | One competitor with its evidence. Free. |
| PATCH | `/competitors/{id}` | `{review_status: confirmed\|rejected\|unreviewed, display_name, review_note}`. Audited. Rejected businesses are skipped by Products. Free. |
| GET | `/products/search?q&market&location&max_merchants(1–10)` | Product evidence across a market's merchant catalogues. Persists observations. |
| GET | `/products?q&market&merchant_id&product_status&limit` | Saved product observations. Free. |
| GET | `/prices/local?product&area&radius(1–100)&reference_store` | Nearby-store price comparison. Persists observations (`discovery_method=price_intelligence`). |
| GET | `/prices/search?q&location` | Legacy Google Shopping search (`market_observations`). |

## Price changes (free)

| Method | Path | Notes |
|---|---|---|
| GET | `/prices/alerts?q&market&location&min_change_percent&outlier_mad_k&dispersion_min_percent` | Alert types: `price_increase`, `price_decrease`, `new_offer`, `not_observed_in_latest`, `outlier`, `price_dispersion`, `conflicting_prices`. Built from stored verified prices only, and each alert cites record ids and source URLs. |
| GET | `/prices/history?product_name`, `/prices/changes?product_name` | Legacy, over `market_observations`. |

## Market signals 💳

| Method | Path | Notes |
|---|---|---|
| GET | `/signals/search-interest?q=a,b(≤5)&geo&date` | Google Trends interest over time. Relative 0–100 within one request; not search volume. Cached 24 h. |
| GET | `/signals/search-interest/regions?q&geo&date&region` | Interest by region (one term). |
| GET | `/signals/search-interest/related?q&geo&date` | Rising and top related queries (one term). |
| GET | `/signals/search-interest/history?q` | Collected comparisons. Free. |
| GET | `/signals/news?q&gl&hl&sort(relevance\|date)` | Google News. Articles deduplicated per query and link. Cached 6 h. |
| GET | `/signals/news/saved?q&limit` | Collected news. Free. |

## Analysis (free)

| Method | Path | Notes |
|---|---|---|
| GET | `/trends/summary`, `/trends/prices`, `/trends/availability`, `/trends/visibility?metric`, `/trends/merchants` | All accept `market`, `location`, and `q` where relevant. |
| GET | `/market-pulse/options`, `/market-pulse?market&location` | A factual snapshot of one market and location. |
| GET | `/analyst/analysis?market&location&include_summary` | Deterministic facts, plus a validated AI summary when a provider is configured. |
| POST | `/analyst/ask` | `{question, market?, location?}`. The answer is built only from numbered evidence (`F1…`), with facts, interpretations, hypotheses and missing data kept separate. When no provider is configured, or an answer fails validation, it falls back to the relevant evidence. |

## Opportunities (free)

| Method | Path | Notes |
|---|---|---|
| GET | `/opportunities/method` | Formula, active weights and disclaimer. |
| GET | `/opportunities?status&market&location&min_score&limit` | Dismissed opportunities are hidden unless `status=dismissed`. |
| POST | `/opportunities/refresh?market&location` | Rebuilds from stored evidence. Review status is kept. |
| PATCH | `/opportunities/{id}` | `{status: new\|saved\|reviewed\|dismissed, note}`. Audited. |

## Reports, saved searches, exports (free)

| Method | Path | Notes |
|---|---|---|
| POST | `/reports` | `{market?, location?, title?}`. Freezes an evidence snapshot. |
| GET | `/reports` | Saved reports. |
| GET | `/reports/{id}.html` | Print-ready report. Use the browser's Save as PDF. |
| DELETE | `/reports/{id}` | Permanent. |
| GET / POST / DELETE | `/saved-searches`, `/saved-searches/{id}` | `module`: research, competitors, products, prices, interest or news. |
| GET | `/export/{competitors\|products\|prices\|price-alerts\|trends\|opportunities}.csv` | Same filters as the matching list endpoint. UTF-8 with BOM; formula injection is neutralised. |
