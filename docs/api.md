> **Superseded.** This early planning note no longer describes the system. See [MarketRadar-Technical-Documentation.md](MarketRadar-Technical-Documentation.md) for the current architecture, API and database, and [audit/](audit/) for module flows.

# API Documentation

## Current Endpoints
- `GET /api/health` - Health check

### `GET /api/prices/search`
- **Purpose**: Retrieves normalized live market pricing observations from SerpApi's Google Shopping engine.
- **Parameters**:
  - `q` (required): The product or category to search for.
  - `location` (optional): Location filter.
- **Example Request**:
  `GET /api/prices/search?q=wireless%20headphones&location=New%20Jersey`
- **Response Structure**:
  ```json
  {
    "query": "wireless headphones",
    "location": "New Jersey",
    "total_results": 1,
    "observations": [
      {
        "product_name": "Test Wireless Headphones",
        "product_id": "12345",
        "merchant": "TechStore",
        "price": 99.99,
        "old_price": 129.99,
        "currency": "$",
        "rating": 4.5,
        "review_count": 120,
        "delivery": "Free delivery",
        "product_link": "https://...",
        "snippet": "Great sound.",
        "position": 1,
        "source": "serpapi_google_shopping",
        "query": "wireless headphones",
        "location": "New Jersey",
        "observed_at": "2023-12-01T12:00:00Z"
      }
    ],
    "source": "serpapi_google_shopping",
    "observed_at": "2023-12-01T12:00:00Z"
  }
  ```
- **Validation / Error States**:
  - `400 Bad Request`: If `q` is missing or empty.
  - `503 Service Unavailable`: If SerpApi is not configured (API key missing). Returns detail: "Live market data is not configured yet..."

## Planned Endpoints
- `GET /api/market/search`
- `GET /api/products/search`
- `GET /api/competitors/search`
- `GET /api/trends/search`
- `GET /api/market-pulse`
- `POST /api/analyst/query`
