"""Location resolution: user input -> canonical provider location.

The provider only accepts a canonical catalogue name, so a raw string must be
resolved before the search rather than forwarded and rejected with
"Unsupported `<location>` location - location parameter."

Every test here is offline. The canonical values asserted below were verified
against the live catalogue once; the point of these tests is the resolution
*logic*, not the catalogue's contents.
"""
import pytest

from app.services.location_service import (
    LocationResolutionError, LocationResolver, candidate_queries,
)


# ------------------------------------------------------------------ candidates
def test_city_is_tried_before_bare_subdivision():
    """"Holmdel, NJ" fails as a whole; "Holmdel" resolves, "NJ" is noise."""
    candidates = candidate_queries("Holmdel, NJ")
    assert candidates == ["Holmdel, NJ", "Holmdel", "NJ"]
    assert candidates.index("Holmdel") < candidates.index("NJ")


def test_postal_code_survives_candidate_generation():
    """A postal code is a first-class catalogue key and must not be stripped."""
    assert candidate_queries("08807") == ["08807"]
    assert "07094" in candidate_queries("10 Meadowlands Pkwy, Secaucus, NJ 07094")


def test_street_address_reduces_to_its_locality():
    candidates = candidate_queries("10 Meadowlands Pkwy, Secaucus, NJ 07094")
    assert "Secaucus" in candidates
    # The locality is tried before the bare postal fallback.
    assert candidates.index("Secaucus") < candidates.index("07094")


def test_candidates_are_deduplicated_and_order_is_stable():
    assert candidate_queries("Austin, Austin") == ["Austin, Austin", "Austin"]
    assert candidate_queries("") == []


# ------------------------------------------------------------------ resolution
class FakeCatalogue:
    """Offline stand-in for locations.json; records every lookup."""

    def __init__(self, table, fail=False):
        self.table = table
        self.fail = fail
        self.lookups = []

    def __call__(self, candidate):
        self.lookups.append(candidate)
        if self.fail:
            raise LocationResolutionError("catalogue unreachable")
        return self.table.get(candidate, [])


def _entry(canonical, target_type="City", country="US"):
    return {"canonical_name": canonical, "target_type": target_type,
            "country_code": country}


def resolver_with(table, fail=False):
    resolver = LocationResolver()
    catalogue = FakeCatalogue(table, fail=fail)
    resolver._lookup = catalogue
    return resolver, catalogue


@pytest.mark.parametrize("raw, candidate, canonical, target", [
    ("Holmdel, NJ", "Holmdel", "Holmdel,New Jersey,United States", "City"),
    ("Secaucus, NJ", "Secaucus", "Secaucus,New Jersey,United States", "City"),
    ("Manasquan, NJ", "Manasquan", "Manasquan,New Jersey,United States", "City"),
    ("08807", "08807", "08807,New Jersey,United States", "Postal Code"),
    ("Austin, Texas", "Austin, Texas", "Austin,Texas,United States", "City"),
    ("Hyderabad", "Hyderabad", "Hyderabad,Telangana,India", "City"),
])
def test_supported_locations_resolve_to_canonical_names(raw, candidate, canonical, target):
    resolver, _ = resolver_with({candidate: [_entry(canonical, target)]})
    resolution = resolver.resolve(raw)
    assert resolution.canonical_name == canonical
    assert resolution.matched_candidate == candidate
    assert resolution.requested == raw


def test_invalid_location_raises_a_readable_error():
    resolver, catalogue = resolver_with({})
    with pytest.raises(LocationResolutionError) as excinfo:
        resolver.resolve("Zzzqqxinvalidplace")
    message = str(excinfo.value)
    # The user sees what to type instead, not the provider's parameter error.
    assert "Zzzqqxinvalidplace" in message
    assert "postal code" in message
    assert "location parameter" not in message


def test_country_code_comes_from_the_catalogue_not_a_default():
    """Generic across countries: nothing here assumes the United States."""
    resolver, _ = resolver_with(
        {"Lyon": [_entry("Lyon,Auvergne-Rhone-Alpes,France", "City", "FR")]})
    assert resolver.resolve("Lyon").country_code == "fr"


def test_catalogue_outage_is_not_reported_as_no_such_place():
    resolver, _ = resolver_with({}, fail=True)
    with pytest.raises(LocationResolutionError) as excinfo:
        resolver.resolve("Holmdel, NJ")
    assert "unreachable" in str(excinfo.value)


def test_district_match_is_a_last_resort_not_a_first_choice():
    """A bare subdivision matches districts first; a real place wins."""
    resolver, _ = resolver_with({
        "Holmdel, NJ": [],
        "Holmdel": [_entry("Holmdel,New Jersey,United States", "City")],
        "NJ": [_entry("NJ-9,New Jersey,United States", "Congressional District")],
    })
    assert resolver.resolve("Holmdel, NJ").target_type == "City"


def test_district_is_still_returned_when_nothing_better_exists():
    resolver, _ = resolver_with(
        {"NJ": [_entry("NJ-9,New Jersey,United States", "Congressional District")]})
    assert resolver.resolve("NJ").canonical_name == "NJ-9,New Jersey,United States"


def test_ambiguous_place_is_surfaced_not_hidden():
    resolver, _ = resolver_with({"Bridgewater": [
        _entry("Bridgewater,New Jersey,United States"),
        _entry("Bridgewater,Massachusetts,United States"),
    ]})
    resolution = resolver.resolve("Bridgewater")
    assert resolution.ambiguous
    assert "Bridgewater,Massachusetts,United States" in resolution.alternatives


def test_resolution_is_cached_so_repeats_cost_nothing():
    resolver, catalogue = resolver_with(
        {"Holmdel": [_entry("Holmdel,New Jersey,United States")]})
    resolver.resolve("Holmdel")
    lookups_after_first = len(catalogue.lookups)
    resolver.resolve("holmdel")
    assert len(catalogue.lookups) == lookups_after_first


def test_failed_resolution_is_cached_too():
    resolver, catalogue = resolver_with({})
    for _ in range(2):
        with pytest.raises(LocationResolutionError):
            resolver.resolve("Zzzqqx")
    assert catalogue.lookups.count("Zzzqqx") == 1


def test_resolve_or_none_degrades_instead_of_failing():
    resolver, _ = resolver_with({})
    assert resolver.resolve_or_none("Zzzqqxinvalidplace") is None


@pytest.mark.parametrize("raw", [
    "Holmdel, NJ", "08807", "Secaucus, NJ", "Manasquan, NJ", "Hyderabad",
])
def test_nothing_is_substituted_when_the_catalogue_knows_nothing(raw):
    """No default city, no previous request's answer, no coordinate fallback.

    An empty catalogue must produce an error for every input -- if any input
    still yielded a location, that location came from us, not the provider.
    """
    resolver, _ = resolver_with({})
    with pytest.raises(LocationResolutionError):
        resolver.resolve(raw)
    assert resolver.resolve_or_none(raw) is None


def test_module_contains_no_hardcoded_coordinates():
    """The removed NJ/Secaucus coordinate fallback must not come back."""
    import ast
    import inspect
    from app.services import location_service

    tree = ast.parse(inspect.getsource(location_service))
    floats = [n.value for n in ast.walk(tree)
              if isinstance(n, ast.Constant) and isinstance(n.value, float)]
    # A latitude/longitude fallback would appear as a float constant; the
    # module legitimately has none.
    assert floats == [], "unexpected coordinate-like constants: " + repr(floats)


def test_candidates_come_only_from_the_users_own_input():
    """No candidate may introduce a place the user did not type."""
    raw = "Holmdel, NJ"
    typed = set(raw.lower().replace(",", " ").split())
    for candidate in candidate_queries(raw):
        assert set(candidate.lower().replace(",", " ").split()) <= typed


def test_lookup_endpoint_is_the_free_catalogue_not_a_search():
    """Resolution must never consume a search credit."""
    from app.services.location_service import SERPAPI_LOCATIONS_URL
    assert SERPAPI_LOCATIONS_URL.endswith("/locations.json")
    assert "search" not in SERPAPI_LOCATIONS_URL
