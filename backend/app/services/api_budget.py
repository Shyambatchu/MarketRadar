import time
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional

import requests
from sqlalchemy.orm import Session
from sqlalchemy import text
from serpapi import GoogleSearch

from app.models.serpapi_models import SearchCache

logger = logging.getLogger("api_budget")
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(message)s'))
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# How long a provider response is reused before a live request is made again.
CACHE_TTL_DAYS = 7

# Seconds before one provider request is abandoned. The client library's own
# default is 60000 seconds, which let a stalled request hold a worker for
# most of a day.
REQUEST_TIMEOUT_SECONDS = 30
# Extra attempts after a transient failure, and the base of the backoff.
MAX_RETRIES = 2
RETRY_BACKOFF_SECONDS = 1.0

# Error kinds. Only "transient" is retried: the others are stable answers
# that repeating the request cannot change.
ERROR_TRANSIENT = "transient"
ERROR_AUTH = "invalid_api_key"
ERROR_QUOTA = "quota_exhausted"
ERROR_REQUEST = "invalid_request"
# A failure we cannot classify. Not retried: an unknown fault repeated is
# more likely to spend time than to succeed.
ERROR_PROVIDER = "provider_error"

_TRANSIENT_MARKERS = ("try again later", "timed out", "timeout",
                      "temporarily", "502", "503", "504")

# SerpApi reports a search that ran and matched nothing through the same
# top-level "error" key as a real failure, while search_metadata.status still
# reads "Success". That is an empty result, never a provider failure.
_EMPTY_RESULT_MARKERS = (
    "hasn't returned any results",
    "has not returned any results",
    "no results found",
)


def is_empty_result(results: dict) -> bool:
    """True when the provider answered successfully with nothing to report."""
    error = str(results.get("error") or "").lower()
    status = str((results.get("search_metadata") or {}).get("status") or "")
    if status.lower() == "error":
        return False
    return any(marker in error for marker in _EMPTY_RESULT_MARKERS)


def classify_error(message: str, exc: Optional[BaseException] = None) -> str:
    """Map a provider failure onto one of the ERROR_* kinds."""
    if isinstance(exc, (requests.Timeout, requests.ConnectionError)):
        return ERROR_TRANSIENT
    text = (message or "").lower()
    if "api key" in text and "invalid" in text:
        return ERROR_AUTH
    if "run out of searches" in text or ("limit" in text and (
            "plan" in text or "hourly" in text or "throughput" in text)):
        return ERROR_QUOTA
    if "unsupported" in text or ("missing" in text and "parameter" in text):
        return ERROR_REQUEST
    if any(marker in text for marker in _TRANSIENT_MARKERS):
        return ERROR_TRANSIENT
    return ERROR_PROVIDER


class ApiBudgetManager:
    def __init__(self, db: Session, api_key: str):
        self.db = db
        self.api_key = api_key
        
        self.used_external = 0
        self.used_website = 0
        self.used_shopping = 0
        self.used_maps = 0
        self.cache_hits = 0

        # Why the most recent live request failed, for callers that need to
        # report the provider's own message rather than a generic failure.
        self.last_error: Optional[str] = None
        # One of the ERROR_* constants, so callers can tell a bad key or an
        # exhausted plan from an outage without parsing provider prose.
        self.last_error_kind: Optional[str] = None

        self._exec_cache: Dict[str, Any] = {}
        # Injectable so tests exercise the retry path without waiting.
        self._sleep = time.sleep

    def _record_usage(self, endpoint: str, query: str) -> int:
        """Atomically records 1 API credit used."""
        sql = text('''
            INSERT INTO api_usage (provider, endpoint, query, success, credits_used)
            VALUES ('serpapi', :endpoint, :query, 0, 1)
        ''')
        result = self.db.execute(sql, {
            "endpoint": endpoint,
            "query": query
        })
        self.db.commit()
        return result.lastrowid

    def _update_reservation(self, usage_id: int, success: bool, response_time: float, credits_used: int):
        sql = text('''
            UPDATE api_usage
            SET success = :success, response_time = :rt, credits_used = :cu
            WHERE id = :usage_id
        ''')
        self.db.execute(sql, {
            "success": 1 if success else 0,
            "rt": response_time,
            "cu": credits_used,
            "usage_id": usage_id
        })
        self.db.commit()

    def _fetch_with_retries(self, params: dict, endpoint: str):
        """(results, error, kind). ``results`` is None when the request failed.

        Transient failures (timeouts, connection errors, the provider's own
        "try again later") are retried with exponential backoff. A bad key, an
        exhausted plan, an invalid request or an unclassified fault is
        returned at once, because repeating it cannot succeed and would only
        add latency.
        """
        error, kind = None, None
        for attempt in range(MAX_RETRIES + 1):
            if attempt:
                self._sleep(RETRY_BACKOFF_SECONDS * (2 ** (attempt - 1)))
            try:
                search = GoogleSearch(params)
                search.timeout = REQUEST_TIMEOUT_SECONDS
                results = search.get_dict()
            except Exception as exc:
                error = str(exc) or type(exc).__name__
                kind = classify_error(error, exc)
            else:
                if not isinstance(results, dict):
                    error, kind = "The provider returned an unreadable response.", ERROR_TRANSIENT
                elif "error" not in results or is_empty_result(results):
                    return results, None, None
                else:
                    error = str(results["error"])
                    kind = classify_error(error)
            if kind != ERROR_TRANSIENT:
                break
            logger.info("[API USAGE] RETRYABLE provider=%s attempt=%d detail=%s",
                        endpoint, attempt + 1, error)
        return None, error, kind

    def _log_budget(self, action: str, provider: str, merchant: str = ""):
        if action == "CACHE HIT":
            msg = f"[API USAGE] CACHE HIT provider={provider}"
            if merchant: msg += f" merchant={merchant}"
            logger.info(msg)
        else:
            msg = f"[API USAGE] LIVE provider={provider}"
            if merchant: msg += f" merchant={merchant}"
            logger.info(msg)

    def _map_provider(self, provider: str) -> str:
        if provider == "merchant_website_indexed": return "website"
        if provider == "google_shopping": return "shopping"
        if provider == "google_maps": return "maps"
        return "external"

    def execute_search(self, cache_key: str, params: dict, endpoint: str, domain: str = "") -> Optional[dict]:
        """Response dict on success, or ``None`` when the provider request failed.

        ``None`` means "we never got an answer" and is deliberately distinct
        from a response carrying zero results: every caller keys its stage
        status off this distinction, so a provider failure must never arrive
        looking like an empty result set. ``last_error`` carries the reason.
        """
        if cache_key in self._exec_cache:
            self.cache_hits += 1
            self._log_budget("CACHE HIT", endpoint, merchant=domain)
            return self._exec_cache[cache_key]
            
        cached = self.db.query(SearchCache).filter(SearchCache.cache_key == cache_key).first()
        if cached and cached.expires_at.replace(tzinfo=timezone.utc) > datetime.now(timezone.utc):
            self.cache_hits += 1
            data = json.loads(cached.response_data)
            self._exec_cache[cache_key] = data
            self._log_budget("CACHE HIT", endpoint, merchant=domain)
            return data

        query_str = params.get("q", "")
        usage_id = self._record_usage(endpoint, query_str)

        mapped_provider = self._map_provider(endpoint)
        setattr(self, f"used_{mapped_provider}", getattr(self, f"used_{mapped_provider}") + 1)
        if mapped_provider != "external":
            self.used_external += 1
        
        self._log_budget("LIVE", endpoint, merchant=domain)
        
        start_time = time.time()
        params["api_key"] = self.api_key
        results, error, kind = self._fetch_with_retries(params, endpoint)
        if results is None:
            # A failed request consumes no search credit at the provider, so
            # the reservation is settled at 0 rather than 1.
            self._update_reservation(usage_id, False, time.time() - start_time, 0)
            self.last_error = error
            self.last_error_kind = kind
            logger.info("[API USAGE] ERROR provider=%s kind=%s detail=%s",
                        endpoint, kind, error)
            return None

        self.last_error = None
        self.last_error_kind = None

        response_time = time.time() - start_time
        self._update_reservation(usage_id, True, response_time, 1)
        
        expires_at = datetime.now(timezone.utc) + timedelta(days=CACHE_TTL_DAYS)
        if cached is not None:
            # An expired row still holds this primary key. Inserting a second
            # one raised IntegrityError after the credit had been spent, so
            # every refresh of an expired search failed. Refresh it in place.
            cached.response_data = json.dumps(results)
            cached.created_at = datetime.now(timezone.utc)
            cached.expires_at = expires_at
        else:
            self.db.add(SearchCache(
                cache_key=cache_key,
                response_data=json.dumps(results),
                expires_at=expires_at,
            ))
        self.db.commit()
        
        self._exec_cache[cache_key] = results
        return results

    def get_usage_report(self) -> dict:
        return {
            "external_calls_used": self.used_external,
            "merchant_discovery_used": self.used_maps,
            "website_provider_used": self.used_website,
            "shopping_used": self.used_shopping,
            "cache_hits": self.cache_hits
        }
