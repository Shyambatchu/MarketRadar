import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.services.api_budget import UsageBudgetExceededError, prune_expired_cache
from app.routes import health, products, prices, competitors, trends, pulse, analyst, serpapi, export, signals, opportunities, reports, dashboard
from app.database.connection import engine
from app.database.base import Base
from app.database.schema_sync import sync_additive_columns
from app.config import settings

# Importing the models package registers every table with Base.metadata;
# without it create_all silently skips models nothing else imports.
import app.models  # noqa: F401

# Create missing tables, then add columns that models gained after their table
# was first created. Both operations are additive: nothing is dropped.
Base.metadata.create_all(bind=engine)
sync_additive_columns(engine, Base.metadata)
# Retention: drop cached provider responses that expired long ago. Usage rows
# and observations are history and are never pruned.
prune_expired_cache(engine)

app = FastAPI(title="MarketRadar API")
logger = logging.getLogger("app")


@app.exception_handler(UsageBudgetExceededError)
def _budget_exceeded(request, exc):
    # Raised from deep inside any credit-spending flow; one handler keeps the
    # answer consistent (429, nothing spent) across every route.
    return JSONResponse(status_code=429, content={"detail": str(exc)})

@app.middleware("http")
async def _unhandled_errors(request: Request, call_next):
    # Registered before CORS, so it runs *inside* it: an unexpected error is
    # logged and returned as a JSON 500 that still carries CORS headers.
    # Starlette's own error page sits outside CORS, so the browser saw a
    # blocked response and the UI wrongly said the backend was unreachable.
    try:
        return await call_next(request)
    except Exception:
        logger.exception("unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content={
            "detail": "The server hit an unexpected error. Details are in the server log."})


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api", tags=["Health"])
app.include_router(products.router, prefix="/api/products", tags=["Products"])
app.include_router(prices.router, prefix="/api/prices", tags=["Prices"])
app.include_router(competitors.router, prefix="/api/competitors", tags=["Competitors"])
app.include_router(trends.router, prefix="/api/trends", tags=["Trends"])
app.include_router(pulse.router, prefix="/api", tags=["Market Pulse"])
app.include_router(analyst.router, prefix="/api/analyst", tags=["AI Analyst"])

app.include_router(serpapi.router, prefix="/api/serpapi", tags=["SerpApi"])
app.include_router(export.router, prefix="/api/export", tags=["Export"])
app.include_router(signals.router, prefix="/api/signals", tags=["Market Signals"])
app.include_router(opportunities.router, prefix="/api/opportunities", tags=["Opportunities"])
app.include_router(reports.router, prefix="/api", tags=["Reports"])
app.include_router(dashboard.router, prefix="/api", tags=["Dashboard"])
