"""Shared test doubles so no test reaches the network or spends a credit."""
from typing import Any, Dict, Optional

from app.services.location_service import (
    LocationResolution, LocationResolutionError, not_found_message,
)

# Canonical forms the real SerpApi catalogue returns for these inputs, verified
# against locations.json. Anything absent is treated as unresolvable.
CANONICAL = {
    "holmdel, nj": ("Holmdel,New Jersey,United States", "us", "City", "Holmdel"),
    "holmdel": ("Holmdel,New Jersey,United States", "us", "City", "Holmdel"),
    "08807": ("08807,New Jersey,United States", "us", "Postal Code", "08807"),
    "07094": ("07094,New Jersey,United States", "us", "Postal Code", "07094"),
    "secaucus, nj": ("Secaucus,New Jersey,United States", "us", "City", "Secaucus"),
    "secaucus": ("Secaucus,New Jersey,United States", "us", "City", "Secaucus"),
    "manasquan, nj": ("Manasquan,New Jersey,United States", "us", "City", "Manasquan"),
    "austin, texas": ("Austin,Texas,United States", "us", "City", "Austin, Texas"),
    "hyderabad": ("Hyderabad,Telangana,India", "in", "City", "Hyderabad"),
    "10 meadowlands pkwy, secaucus, nj 07094": (
        "Secaucus,New Jersey,United States", "us", "City", "Secaucus"),
}


class StubResolver:
    """Offline stand-in for LocationResolver with the same contract."""

    def __init__(self, table: Optional[Dict] = None, unreachable: bool = False):
        self.table = table if table is not None else CANONICAL
        self.unreachable = unreachable
        self.calls = []

    def resolve(self, raw: str) -> LocationResolution:
        self.calls.append(raw)
        if self.unreachable:
            raise LocationResolutionError(
                "The location catalogue could not be reached, so '" + str(raw)
                + "' could not be verified. Try again in a moment.")
        key = (raw or "").strip().lower()
        if key not in self.table:
            raise LocationResolutionError(not_found_message(raw))
        canonical, country, target, candidate = self.table[key]
        return LocationResolution(requested=raw, canonical_name=canonical,
                                  country_code=country, target_type=target,
                                  matched_candidate=candidate)

    def resolve_or_none(self, raw: str) -> Optional[LocationResolution]:
        try:
            return self.resolve(raw)
        except LocationResolutionError:
            return None


def no_account(api_key, timeout: int = 10) -> Dict[str, Any]:
    """Account quota unavailable: every field null, nothing invented."""
    from app.services.serpapi_account import _ACCOUNT_FIELDS
    out: Dict[str, Any] = {name: None for name in _ACCOUNT_FIELDS}
    out["account_quota_available"] = False
    out["account_quota_detail"] = "stubbed: account endpoint not called"
    return out


def account_quota(**overrides) -> Dict[str, Any]:
    """A plausible account.json payload, shaped like the real response."""
    payload = {
        "plan_name": "Free Plan",
        "account_status": "Active",
        "plan_renewal_date": "2026-10-19",
        "searches_per_month": 250,
        "plan_searches_left": 133,
        "extra_credits": 1000,
        "total_searches_left": 1133,
        "this_month_usage": 117,
        "this_hour_searches": 3,
        "account_rate_limit_per_hour": 200000,
    }
    payload.update(overrides)
    payload["account_quota_available"] = payload["total_searches_left"] is not None
    payload["account_quota_detail"] = None
    return payload
