"""SerpApi account quota -- the only authoritative source of what remains.

``account.json`` reports the account's real plan, usage and remaining searches.
It is an account endpoint, not a search engine: calling it does not consume a
search credit, so usage can be reported without spending anything.

No figure here is ever derived, estimated or pro-rated. In particular a daily
allowance is never computed from a monthly quota: SerpApi bills per month and
per hour, and inventing a daily number would be exactly the artificial budget
that was removed (spec 34). Anything the provider does not report stays
``None`` so the UI can say "Unavailable".
"""
import logging
from typing import Any, Dict, Optional

import requests

logger = logging.getLogger("serpapi_account")

SERPAPI_ACCOUNT_URL = "https://serpapi.com/account.json"

# Quota fields copied straight through from the provider, never recomputed.
# Anything absent from the response stays None.
_ACCOUNT_FIELDS = (
    "plan_name",
    "account_status",
    "plan_renewal_date",
    "searches_per_month",
    "plan_searches_left",
    "extra_credits",
    "total_searches_left",
    "this_month_usage",
    "this_hour_searches",
    "account_rate_limit_per_hour",
)

_UNAVAILABLE: Dict[str, Any] = {name: None for name in _ACCOUNT_FIELDS}


def _empty(reason: Optional[str]) -> Dict[str, Any]:
    out = dict(_UNAVAILABLE)
    out["account_quota_available"] = False
    out["account_quota_detail"] = reason
    return out


def fetch_account_usage(api_key: Optional[str], timeout: int = 10) -> Dict[str, Any]:
    """Provider quota, or every field ``None`` when it cannot be read.

    Never raises: a usage panel must not be what breaks a page, and an
    unreachable account endpoint says nothing about whether searching works.
    """
    if not api_key:
        return _empty("SerpApi key is not configured.")

    try:
        # The key travels as a query parameter because that is the only form the
        # endpoint accepts; it is never logged or returned to the client.
        resp = requests.get(SERPAPI_ACCOUNT_URL, params={"api_key": api_key},
                            timeout=timeout)
        if not resp.ok:
            return _empty("SerpApi account endpoint returned HTTP "
                          + str(resp.status_code) + ".")
        data = resp.json()
    except Exception as exc:
        logger.warning("SerpApi account lookup failed: %s", type(exc).__name__)
        return _empty("SerpApi account quota could not be retrieved.")

    if not isinstance(data, dict):
        return _empty("SerpApi account quota could not be retrieved.")

    out: Dict[str, Any] = {name: data.get(name) for name in _ACCOUNT_FIELDS}
    out["account_quota_available"] = out["total_searches_left"] is not None
    out["account_quota_detail"] = None if out["account_quota_available"] else \
        "SerpApi did not report a remaining search count."
    return out
