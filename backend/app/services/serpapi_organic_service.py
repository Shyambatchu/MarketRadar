import os
import json
import time
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.serpapi_models import SerpSearch, SerpSearchResult, SerpLocalResult
from app.services.api_budget import ApiBudgetManager
from app.services.location_service import (
    LocationResolutionError, default_resolver,
)
from app.services.serpapi_account import fetch_account_usage

class SerpApiNotConfiguredError(Exception):
    pass

class SerpApiLimitExceededError(Exception):
    pass

class SerpApiProviderError(Exception):
    """The provider request failed. Distinct from a search that found nothing."""

class SerpApiOrganicService:
    def __init__(self, db: Session, api_key: str = None, resolver=None,
                 account_fetcher=None):
        self.db = db
        self.api_key = api_key
        if not self.api_key:
            self.api_key = os.environ.get("SERPAPI_API_KEY")

        self.budget = ApiBudgetManager(db, self.api_key) if self.api_key else None
        self.resolver = resolver or default_resolver
        # Injectable so tests can report usage without reaching the network.
        self.account_fetcher = account_fetcher or fetch_account_usage

    def search_google(self, query: str, location: str = None, num: int = 10,
                      start: int = 0, hl: str = "en", gl: str = "us",
                      google_domain: str = "google.com"):
        if not self.api_key or not self.budget:
            raise SerpApiNotConfiguredError("Live market data is not configured yet. SerpApi integration is ready.")

        # The provider only accepts a canonical catalogue location, so a raw
        # user string ("Holmdel, NJ") is resolved before the search rather than
        # forwarded and rejected. Resolution costs no search credit; failure
        # raises LocationResolutionError for a readable message upstream.
        resolution = self.resolver.resolve(location) if location else None
        provider_location = resolution.canonical_name if resolution else None

        # Language, country, Google domain and the *resolved* location all
        # materially change the results, so they belong in the cache identity:
        # one market must never serve another market's response.
        cache_key = (f"v3|google|{query}|{provider_location}|{num}|{start}"
                     f"|{hl}|{gl}|{google_domain}")

        params = {
            "engine": "google",
            "q": query,
            "num": num,
            "start": start,
            "hl": hl,
            "gl": gl,
            "google_domain": google_domain,
        }
        if provider_location:
            params["location"] = provider_location

        start_time = time.time()

        # The cache manager knows whether it served this; elapsed time does not.
        hits_before = self.budget.cache_hits
        raw_results = self.budget.execute_search(cache_key, params, "google_organic")

        if raw_results is None:
            # A provider failure stays a failure: it is never reported as a
            # successful search that happened to return nothing.
            raise SerpApiProviderError(
                self.budget.last_error or "The search provider did not respond.")

        response_time = time.time() - start_time
        cache_hit = self.budget.cache_hits > hits_before

        return self._process_response(raw_results, query, location, cache_hit=cache_hit,
                                      response_time=response_time, resolution=resolution)

    def _process_response(self, raw_results: dict, query: str, location: str, cache_hit: bool,
                          response_time: float = 0.0, resolution=None):
        # A provider payload is untrusted shape: a null or non-list section is
        # read as empty rather than crashing the request with a 500.
        organic = raw_results.get("organic_results") or []
        local = raw_results.get("local_results") or []
        if not isinstance(organic, list):
            organic = []
        organic = [o for o in organic if isinstance(o, dict)]
        
        search_record = SerpSearch(
            query=query,
            location=location,
            engine="google",
            status="success",
            response_time=response_time,
            cache_hit=cache_hit,
            credits_used=0 if cache_hit else 1
        )
        self.db.add(search_record)
        self.db.flush()
        
        parsed_results = []
        for org in organic:
            link = org.get("link", "")
            domain = urlparse(link).netloc if link else None
            
            res = SerpSearchResult(
                search_id=search_record.id,
                position=org.get("position"),
                title=org.get("title"),
                link=link,
                displayed_link=org.get("displayed_link"),
                snippet=org.get("snippet"),
                domain=domain,
                result_type="organic"
            )
            self.db.add(res)
            
            parsed_results.append({
                "position": res.position,
                "title": res.title,
                "link": res.link,
                "displayed_link": res.displayed_link,
                "snippet": res.snippet,
                "domain": res.domain,
                "result_type": res.result_type
            })
            
        if isinstance(local, dict):
            places = local.get("places") or []
        else:
            places = local if isinstance(local, list) else []
        parsed_local_results = []
        for p in (p for p in places if isinstance(p, dict)):
            type_str = p.get("type", "")
            addr_str = p.get("address", "")
            
            # SerpApi returns a place's site either at the top level or nested
            # under "links", depending on the engine. Reading only one shape
            # silently dropped the website -- and with it the domain, which is
            # the strongest identity signal downstream.
            links = p.get("links") or {}
            website = p.get("website") or links.get("website")
            gps = p.get("gps_coordinates") or {}
            local_res = SerpLocalResult(
                search_id=search_record.id,
                position=p.get("position"),
                title=p.get("title"),
                type=type_str,
                rating=p.get("rating"),
                reviews=p.get("reviews"),
                address=addr_str,
                phone=p.get("phone"),
                website=website,
                place_id=p.get("place_id"),
                latitude=gps.get("latitude"),
                longitude=gps.get("longitude"),
            )
            self.db.add(local_res)
            parsed_local_results.append({
                "position": local_res.position,
                "title": local_res.title,
                "type": local_res.type,
                "rating": local_res.rating,
                "reviews": local_res.reviews,
                "address": local_res.address,
                "phone": local_res.phone,
                "website": local_res.website,
                "place_id": local_res.place_id,
                "latitude": local_res.latitude,
                "longitude": local_res.longitude,
            })

        self.db.commit()

        return {
            "query": query,
            # What the user asked for, and what the provider was actually given.
            "location": location,
            "resolved_location": resolution.canonical_name if resolution else None,
            "location_resolution": resolution.as_dict() if resolution else None,
            "engine": "google",
            "searched_at": search_record.searched_at,
            "cache_hit": cache_hit,
            # A search that ran and found nothing is not the same as one that
            # failed; the latter never reaches here (spec 5).
            "provider_status": "success" if parsed_results or parsed_local_results else "no_results",
            "results": parsed_results,
            "local_results": parsed_local_results
        }
        
    def get_usage_stats(self):
        """Local request history plus SerpApi's own authoritative quota.

        Two independent things, never conflated:

        * local_* -- what this application observed itself doing.
        * account -- SerpApi's account quota, the only authoritative source of
          how many searches remain. Read from the Account API, which is not a
          search and so consumes no search credit.

        There is no artificial application-level budget (spec 34): nothing here
        is a limit, and no quota figure is ever derived or estimated. When the
        Account API cannot be reached every account field is ``None``, so the
        caller renders "Unavailable" rather than a guess or a blank.
        """
        row = self.db.execute(text(
            "SELECT COUNT(*), COALESCE(SUM(credits_used), 0),"
            " COALESCE(SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END), 0)"
            " FROM api_usage"
        )).first()
        cache_row = self.db.execute(text(
            "SELECT COALESCE(SUM(CASE WHEN cache_hit THEN 1 ELSE 0 END), 0)"
            " FROM serp_searches"
        )).first()

        stats = {
            "local_requests_recorded": int(row[0] or 0),
            "local_credits_used": int(row[1] or 0),
            "local_failed_requests": int(row[2] or 0),
            "local_cache_hits": int(cache_row[0] or 0),
        }
        stats.update(self.account_fetcher(self.api_key))
        return stats

    def get_recent_searches(self, limit: int = 5):
        searches = self.db.query(SerpSearch).order_by(SerpSearch.searched_at.desc()).limit(limit).all()
        result = []
        for s in searches:
            if not any(r['query'] == s.query for r in result):
                result.append({
                    "id": s.id,
                    "query": s.query,
                    "location": s.location,
                    "searched_at": s.searched_at,
                    "organic_count": len(s.results),
                    "local_count": len(s.local_results)
                })
        return result
