"""Generic resolution of a user-entered location to a provider-supported one.

SerpApi's ``location`` parameter only accepts a canonical name from its own
location catalogue. A raw user string is rejected outright, e.g.
"Unsupported 'Holmdel, NJ' location - location parameter."

``locations.json`` is a free catalogue lookup: it is not a search, so it costs
no search credit and needs no API key. The catalogue is indexed by place name
and by postal code, but *not* by "City, <subdivision abbreviation>" -- the form
people actually type. So a single lookup of the raw string usually fails while
a lookup of one of its components succeeds::

    "Holmdel, NJ"                            -> 0 results
    "Holmdel"                                -> Holmdel,New Jersey,United States
    "08807"                                  -> 08807,New Jersey,United States
    "10 Meadowlands Pkwy, Secaucus, NJ 07094"-> 0 results
    "Secaucus"                               -> Secaucus,New Jersey,United States

Resolution therefore tries the raw string first, then progressively narrower
component windows, then any standalone postal code. Nothing here names a
country, subdivision, city or coordinate: the candidate set is derived from the
user's own input, so the same code resolves Hyderabad and Lyon as well as
Holmdel.
"""
import re
import threading
import unicodedata
from typing import Dict, List, Optional

import requests

SERPAPI_LOCATIONS_URL = "https://serpapi.com/locations.json"

# Maximum catalogue lookups per resolution, bounding latency on a long string.
MAX_CANDIDATES = 6

# SerpApi's own target_type taxonomy, most place-like first. Used only to pick
# between results the catalogue already returned -- never to invent a location.
_PREFERRED_TARGET_TYPES = [
    "Postal Code", "City", "Municipality", "Borough", "Town", "Village",
    "Neighborhood", "County", "Province", "State", "Territory",
    "Autonomous Community", "Region", "Department", "Prefecture", "Country",
]
# Targets that sit inside a place but are not the place: a bare subdivision
# abbreviation matches these before it matches anything useful.
_DEMOTED_TARGET_TYPES = {
    "Congressional District", "Airport", "University", "TV Region",
}

_POSTAL_TOKEN_RE = re.compile(r"^[0-9]{4,10}$")


class LocationResolutionError(Exception):
    """The requested location has no provider-supported equivalent.

    Raised instead of forwarding a raw string the provider will reject, so the
    caller can return a readable message rather than surfacing the provider's
    own "Unsupported ... location - location parameter."
    """


class LocationConflictError(LocationResolutionError):
    """The input resolved only by discarding a component that contradicts it.

    Unlike an outage this is a stable answer about the input, so it is cached.
    """


class LocationResolution:
    """Outcome of resolving one user-entered location."""

    def __init__(self, requested: str, canonical_name: str, country_code: Optional[str],
                 target_type: Optional[str], matched_candidate: str,
                 alternatives: Optional[List[str]] = None):
        self.requested = requested
        self.canonical_name = canonical_name
        self.country_code = country_code
        self.target_type = target_type
        self.matched_candidate = matched_candidate
        self.alternatives = alternatives or []

    @property
    def ambiguous(self) -> bool:
        return bool(self.alternatives)

    def as_dict(self) -> Dict:
        return {
            "requested": self.requested,
            "canonical_name": self.canonical_name,
            "country_code": self.country_code,
            "target_type": self.target_type,
            "matched_candidate": self.matched_candidate,
            "ambiguous": self.ambiguous,
            "alternatives": self.alternatives,
        }


def candidate_queries(raw: str) -> List[str]:
    """Catalogue lookups to try for ``raw``, most specific first.

    Derived purely from the user's input: the whole string, then every
    contiguous run of comma-separated components (longer runs first, so a city
    is tried before a bare subdivision), then any standalone postal code.
    """
    raw = (raw or "").strip()
    if not raw:
        return []

    parts = [p.strip() for p in raw.split(",") if p.strip()]
    candidates: List[str] = [raw]

    # Longer component runs first; within a length, left-most first. For
    # "Holmdel, NJ" this yields "Holmdel" before "NJ".
    for size in range(len(parts) - 1, 0, -1):
        for start in range(0, len(parts) - size + 1):
            candidates.append(", ".join(parts[start:start + size]))

    # A postal code is the catalogue's most precise key, but it only matches
    # when looked up on its own ("NJ 07094" fails, "07094" succeeds).
    for token in re.split(r"[\s,]+", raw):
        if _POSTAL_TOKEN_RE.match(token):
            candidates.append(token)

    seen = set()
    ordered = []
    for c in candidates:
        if c and c.lower() not in seen:
            seen.add(c.lower())
            ordered.append(c)
    return ordered


def _rank(result: Dict) -> int:
    target = result.get("target_type") or ""
    if target in _DEMOTED_TARGET_TYPES:
        return len(_PREFERRED_TARGET_TYPES) + 1
    try:
        return _PREFERRED_TARGET_TYPES.index(target)
    except ValueError:
        return len(_PREFERRED_TARGET_TYPES)


def _fold(text: str) -> str:
    """Case-, accent- and spacing-insensitive form for comparing place names."""
    decomposed = unicodedata.normalize("NFKD", text or "")
    plain = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", plain.lower()).strip()


def _leading_name(result: Dict) -> str:
    """The place a catalogue entry names, without its containing regions."""
    return _fold((result.get("canonical_name") or "").split(",")[0])


def _contradicted_component(raw: str, candidate: str, canonical: str) -> Optional[str]:
    """A typed component the resolved location does not account for, if any.

    Only components that were discarded to reach ``candidate`` are checked.
    Components holding digits (street lines, postal codes) and short
    abbreviations ("NJ", "TX", "UK") cannot be verified against a canonical
    name and are allowed through; anything longer must appear in it.
    """
    used = {_fold(p) for p in candidate.split(",")}
    resolved = _fold(canonical)
    for part in (p.strip() for p in raw.split(",")):
        folded = _fold(part)
        if not folded or folded in used:
            continue
        if any(ch.isdigit() for ch in folded) or len(folded.replace(" ", "")) <= 3:
            continue
        if folded not in resolved:
            return part
    return None


def not_found_message(raw: str) -> str:
    return (
        "'" + (raw or "").strip() + "' could not be matched to a supported "
        "search location. Try a city, a postal code, or a city with its full "
        "state or region name (for example 'Holmdel, New Jersey' rather than "
        "'Holmdel, NJ')."
    )


class LocationResolver:
    """Caches catalogue lookups; the catalogue is effectively static."""

    def __init__(self, timeout: int = 10):
        self.timeout = timeout
        # A resolution, None for "no such place", or a conflict message.
        self._cache: Dict[str, object] = {}
        self._lock = threading.Lock()

    def _lookup(self, candidate: str) -> List[Dict]:
        try:
            resp = requests.get(SERPAPI_LOCATIONS_URL,
                                params={"q": candidate, "limit": 5},
                                timeout=self.timeout)
            # An HTTP error is an outage, not "no such place". Returning [] here
            # used to cache the location as unresolvable for the process lifetime.
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            # A catalogue outage must not be reported as "no such place".
            raise LocationResolutionError(
                "The location catalogue could not be reached, so '" + candidate +
                "' could not be verified. Try again in a moment.")
        return data if isinstance(data, list) else []

    def resolve(self, raw: str) -> LocationResolution:
        """Canonical provider location for ``raw``, else LocationResolutionError."""
        key = (raw or "").strip().lower()
        if not key:
            raise LocationResolutionError("No location was provided.")

        with self._lock:
            if key in self._cache:
                cached = self._cache[key]
                if cached is None:
                    raise LocationResolutionError(not_found_message(raw))
                if isinstance(cached, str):
                    raise LocationConflictError(cached)
                return cached

        try:
            resolution = self._resolve_uncached(raw)
        except LocationConflictError as exc:
            with self._lock:
                self._cache[key] = str(exc)
            raise

        with self._lock:
            self._cache[key] = resolution
        if resolution is None:
            raise LocationResolutionError(not_found_message(raw))
        return resolution

    def resolve_or_none(self, raw: str) -> Optional[LocationResolution]:
        """As ``resolve``, but an unresolvable location is not an error.

        For a provider where localisation is an enhancement rather than the
        point of the request, an unresolved location degrades the result; it
        does not fail it.
        """
        try:
            return self.resolve(raw)
        except LocationResolutionError:
            return None

    def _resolve_uncached(self, raw: str) -> Optional[LocationResolution]:
        weak: Optional[LocationResolution] = None

        for candidate in candidate_queries(raw)[:MAX_CANDIDATES]:
            results = [r for r in self._lookup(candidate) if r.get("canonical_name")]
            if not results:
                continue

            # A result that *is* the place typed beats one merely inside it:
            # "Texas" must resolve to the state, not to Dallas. Among those the
            # catalogue's own order is kept. Only when nothing is named exactly
            # does the target-type ranking choose.
            named = [r for r in results if _leading_name(r) == _fold(candidate)]
            if named:
                best = named[0]
                alternatives = [r["canonical_name"] for r in named[1:]]
            else:
                results = sorted(results, key=_rank)
                best = results[0]
                alternatives = [r["canonical_name"] for r in results[1:]
                                if _rank(r) == _rank(best)]
            canonical = best["canonical_name"]

            # Resolving one component must not silently drop another that
            # contradicts it: "Xyzzyville, New Jersey" is not Newark, and
            # "Holmdel, Germany" is not Holmdel, New Jersey.
            conflict = _contradicted_component(raw, candidate, canonical)
            if conflict:
                raise LocationConflictError(
                    "'" + raw.strip() + "' could not be matched as typed: '"
                    + conflict + "' does not match the closest supported "
                    "location, " + canonical.replace(",", ", ") + ". Check the "
                    "spelling, or search for that location directly.")
            resolution = LocationResolution(
                requested=raw,
                canonical_name=canonical,
                country_code=(best.get("country_code") or "").lower() or None,
                target_type=best.get("target_type"),
                matched_candidate=candidate,
                alternatives=alternatives,
            )

            # A bare subdivision abbreviation matches districts and airports
            # before it matches a place. Keep looking, but do not discard it.
            if best.get("target_type") in _DEMOTED_TARGET_TYPES:
                weak = weak or resolution
                continue
            return resolution

        return weak


# One process-wide resolver so the catalogue cache is shared across requests.
default_resolver = LocationResolver()
