from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import health, market, products, prices, competitors, trends, pulse, analyst, serpapi
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

app = FastAPI(title="MarketRadar API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api", tags=["Health"])
app.include_router(market.router, prefix="/api/market", tags=["Market"])
app.include_router(products.router, prefix="/api/products", tags=["Products"])
app.include_router(prices.router, prefix="/api/prices", tags=["Prices"])
app.include_router(competitors.router, prefix="/api/competitors", tags=["Competitors"])
app.include_router(trends.router, prefix="/api/trends", tags=["Trends"])
app.include_router(pulse.router, prefix="/api", tags=["Market Pulse"])
app.include_router(analyst.router, prefix="/api/analyst", tags=["AI Analyst"])

app.include_router(serpapi.router, prefix="/api/serpapi", tags=["SerpApi"])
