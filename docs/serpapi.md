> **Superseded.** This early planning note no longer describes the system. See [MarketRadar-Technical-Documentation.md](MarketRadar-Technical-Documentation.md) for the current architecture, API and database, and [audit/](audit/) for module flows.

# SerpApi Integration

Planned usage of SerpApi:
- **Google Shopping**: To gather observed competitor prices and product availability signals.
- **Google Search**: For generic market pulses and search ranking signals.
- **Google Maps**: To identify local competitors.
- **Google Trends**: For observing regional interest over time.

## Google Shopping Integration

### Data Flow
1. **SerpApi**: MarketRadar calls SerpApi's Google Shopping engine.
2. **Raw response**: SerpApi returns a complex JSON payload representing the search results.
3. **Normalization**: The raw response is processed by `NormalizationService`, stripping away API-specific structures, handling missing values gracefully (e.g. products without prices or ratings), and generating a standard internal format.
4. **MarketRadar observation**: The resulting array of `PriceObservation` schemas is consumed by the frontend to render the Price Intelligence module.

*Note: Live data via SerpApi is currently pending API key configuration and is NOT yet available in the deployed application.*
