"""Request bounds shared by the routes.

Checked by hand rather than with ``Query(ge=..., le=...)`` because FastAPI's
validation answers 422, which this API reserves for a location that has no
provider-supported equivalent -- a distinction the frontend depends on. An
out-of-range parameter is an unusable request, so it is a 400.
"""
from fastapi import HTTPException

# Results per Google search. SerpApi bills one credit per request whatever the
# size, but the provider caps a page at 100.
MAX_RESULTS_PER_SEARCH = 100
# Merchant catalogues searched per product search, one credit each.
MAX_MERCHANTS_PER_SEARCH = 10
# Rows returned by a saved-record listing.
MAX_LIST_LIMIT = 500


def require_range(name: str, value: int, low: int, high: int) -> int:
    if value is None or not low <= value <= high:
        raise HTTPException(
            status_code=400,
            detail="'" + name + "' must be between " + str(low) + " and "
            + str(high) + ".")
    return value
