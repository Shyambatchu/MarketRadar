> **Superseded.** This early planning note no longer describes the system. See [MarketRadar-Technical-Documentation.md](MarketRadar-Technical-Documentation.md) for the current architecture, API and database, and [audit/](audit/) for module flows.

# Database Documentation

Using SQLite for the initial MVP to reduce server setup and keep things persistent locally.

## Planned Tables
- **Business**: `id, name, industry, market, created_at`
- **Product**: `id, business_id, name, brand, category, sku, created_at`
- **Merchant**: `id, name, domain, location, latitude, longitude, source, created_at`
- **MarketObservation**: `id, business_id, product_id, merchant_id, query, price, currency, rating, review_count, availability_signal, source, location, observed_at`
- **TrendObservation**: `id, business_id, keyword, region, interest_value, period, source, observed_at`
- **MarketEvent**: `id, business_id, event_type, title, description, severity, evidence, detected_at`
