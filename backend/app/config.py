from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, List
import os

class Settings(BaseSettings):
    SERPAPI_API_KEY: Optional[str] = None

    # AI Analyst. Optional: without these the analyst still returns its
    # deterministic factual analysis, only the narrative summary is withheld.
    AI_PROVIDER: str = ""
    AI_API_KEY: Optional[str] = None
    AI_MODEL: Optional[str] = None
    DATABASE_URL: str = "sqlite:///./data/market_radar.db"
    FRONTEND_URL: Optional[str] = None
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:5174,http://127.0.0.1:5173,http://127.0.0.1:5174"

    # Optional application-level cap on live SerpApi searches per calendar
    # month (UTC). Unset by default: SerpApi's own account quota is the
    # authoritative limit. When set, a live search beyond it is refused (429)
    # before any credit is spent; cached responses are always served.
    SERPAPI_MONTHLY_BUDGET: Optional[int] = None
    # Cost estimate inputs. When unset, the plan reported by SerpApi's account
    # endpoint is priced from the published table in services/usage_service.py.
    SERPAPI_PLAN_MONTHLY_PRICE_USD: Optional[float] = None
    SERPAPI_PLAN_SEARCHES_PER_MONTH: Optional[int] = None

    # Opportunity score weights (normalised to sum to 1 when used) and the
    # half-life, in days, of the freshness input.
    OPPORTUNITY_WEIGHT_IMPACT: float = 0.40
    OPPORTUNITY_WEIGHT_CONFIDENCE: float = 0.30
    OPPORTUNITY_WEIGHT_FRESHNESS: float = 0.15
    OPPORTUNITY_WEIGHT_RELEVANCE: float = 0.15
    OPPORTUNITY_FRESHNESS_HALF_LIFE_DAYS: float = 14.0

    # Price change detection thresholds (all overridable per request).
    PRICE_CHANGE_MIN_PERCENT: float = 5.0
    PRICE_OUTLIER_MAD_K: float = 3.5
    PRICE_OUTLIER_MIN_MERCHANTS: int = 4
    PRICE_DISPERSION_MIN_PERCENT: float = 25.0

    @field_validator("*", mode="before")
    @classmethod
    def _blank_is_unset(cls, value, info):
        # A blank line in .env ("SERPAPI_MONTHLY_BUDGET=") means "not set", not
        # an unparseable number. Required strings keep their blank value.
        if value == "" and cls.model_fields[info.field_name].default is None:
            return None
        return value

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
