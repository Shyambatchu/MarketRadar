import os
from sqlalchemy.orm import Session
from app.services.api_budget import ApiBudgetManager
from app.services.location_service import default_resolver

class SerpApiNotConfiguredError(Exception):
    pass

class SerpApiService:
    def __init__(self, db: Session, api_key: str = None, resolver=None):
        self.db = db
        self.api_key = api_key
        self.resolver = resolver or default_resolver

    def search_google_shopping(self, query: str, location: str = None):
        if not self.api_key:
            raise SerpApiNotConfiguredError("Live market data is not configured yet. SerpApi integration is ready. Add the API key to begin collecting market observations.")

        budget = ApiBudgetManager(self.db, self.api_key)

        # Google Shopping rejects anything but a canonical catalogue location,
        # so the raw string is resolved first. Localisation is an enhancement
        # here, not the request itself, so an unresolvable location produces an
        # unlocalised search rather than an error.
        resolution = self.resolver.resolve_or_none(location) if location else None
        provider_location = resolution.canonical_name if resolution else None

        params = {
            "engine": "google_shopping",
            "q": query,
            "api_key": self.api_key
        }
        if provider_location:
            params["location"] = provider_location

        # Cache identity mirrors the resolved request, not the raw input: two
        # spellings of one place must share a response, and two different places
        # must never share one.
        cache_key = f"shopping_legacy|v2|{query}|{provider_location}"

        results = budget.execute_search(cache_key, params, "google_shopping")
        if results is None:
            # The provider failed; that is never reported as zero results.
            raise Exception("Failed to fetch market data: "
                            + (budget.last_error or "the provider did not respond."))

        return results

    def search_google(self):
        pass

    def search_google_maps(self):
        pass

    def search_google_trends(self):
        pass
