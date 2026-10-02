from pydantic_settings import BaseSettings
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

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
