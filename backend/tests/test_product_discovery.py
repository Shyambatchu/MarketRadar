"""Products: product evidence across the merchants in a market.

Offline throughout -- the SerpApi client, the location catalogue and the
account endpoint are stubbed, but the real ``ApiBudgetManager``,
``CompetitorService``, ``MerchantWebsitePriceProvider`` and
``product_identity.match_product`` all run, so the contracts between them are
verified rather than assumed.

Industries are varied on purpose (coffee, automotive parts, consumer
electronics, fitness) so nothing can become specific to one market.
"""
import pytest
from unittest.mock import patch
from sqlalchemy import text

from app.database.base import Base
from app.database.connection import SessionLocal, engine
from app.models.merchant import Merchant
from app.models.product_observation import ProductObservation
from app.services.competitor_service import CompetitorService
from app.services.location_service import LocationResolutionError
from app.services.product_service import ProductService
from app.services.serpapi_organic_service import (
    SerpApiOrganicService, SerpApiProviderError,
)

from tests.stubs import StubResolver, no_account


@pytest.fixture
def db():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    for table in ("search_cache", "product_observations",
                  "competitor_observations", "merchants"):
        session.execute(text("DELETE FROM " + table))
    session.commit()
    yield session
    session.close()


@pytest.fixture
def service(db):
    organic = SerpApiOrganicService(api_key="test_key", db=db,
                                   resolver=StubResolver(),
                                   account_fetcher=no_account)
    competitors = CompetitorService(db=db, organic_service=organic)
    return ProductService(db=db, competitor_service=competitors)


def local(title, website, place_id="p1", address="1 Main St", position=1):
    return {"title": title, "website": website, "place_id": place_id,
            "address": address, "position": position}


def organic(title, link, snippet="", position=1):
    return {"title": title, "link": link, "snippet": snippet, "position": position}


MERCHANT = [local("Rivertown Supply", "https://rivertown.example", place_id="p1")]


class Router:
    """Routes each SerpApi call by its query: discovery vs site: lookups."""

    def __init__(self, discovery, per_site, failing_sites=()):
        self.discovery = discovery
        self.per_site = per_site
        self.failing_sites = set(failing_sites)
        self.queries = []

    def __call__(self, params):
        q = params.get("q", "")
        self.queries.append(q)
        outer = self

        class Search:
            @staticmethod
            def get_dict():
                if q.startswith("site:"):
                    domain = q.split()[0][len("site:"):]
                    if domain in outer.failing_sites:
                        raise RuntimeError("provider down for " + domain)
                    return {"organic_results": outer.per_site.get(domain, [])}
                return outer.discovery

        return Search()


def run(service, product, site_rows=None, merchants=MERCHANT, organic_rows=(),
        failing_sites=(), market="Household Supplies",
        location="Austin, Texas", **kwargs):
    discovery = {"local_results": list(merchants),
                 "organic_results": list(organic_rows)}
    router = Router(discovery, site_rows or {}, failing_sites)
    with patch("app.services.api_budget.GoogleSearch", side_effect=router):
        result = service.discover(product=product, market=market,
                                  location=location, **kwargs)
    return result, router


def stage(result, name):
    return next((s for s in result.stages if s.stage == name), None)


# ============================================================ 1,19: reuse
def test_location_resolution_is_delegated_not_reimplemented(service):
    result, _ = run(service, "Widget 2000")
    assert result.location_resolved == "Austin,Texas,United States"
    assert stage(result, "location_resolution").status == "ok"


def test_products_implements_no_resolver_matcher_or_product_identity():
    """Spec: no second resolver, merchant matcher or product matcher."""
    import inspect
    from app.services import product_service

    source = inspect.getsource(product_service)
    assert "locations.json" not in source
    assert "class LocationResolver" not in source
    assert "def match_merchant" not in source
    assert "def match_product" not in source
    # It must call the shared ones instead.
    assert "from app.services.product_identity import" in source
    assert "from app.services.competitor_service import" in source


def test_unresolvable_location_is_not_an_empty_product_result(service):
    with patch("app.services.api_budget.GoogleSearch") as MockSearch:
        with pytest.raises(LocationResolutionError):
            service.discover(product="Widget 2000", market="Household Supplies",
                             location="Zzzqqxinvalidplace")
        assert MockSearch.call_count == 0


# ============================================================ 2: exact match
def test_exact_product_match_on_a_product_page_verifies_a_price(service, db):
    """Coffee: identity holds, page is a product page, one clear price."""
    result, _ = run(service, "Ridgeline Dark Roast 340g", site_rows={
        "rivertown.example": [organic(
            "Ridgeline Dark Roast 340g",
            "https://rivertown.example/product/ridgeline-dark-roast-340g",
            "Ridgeline Dark Roast 340g $14.99 add to cart")]},
        market="Coffee")

    assert result.products_found == 1
    e = result.evidence[0]
    assert e.product_status == "found"
    assert e.price_status == "verified"
    assert e.price == 14.99
    assert e.observed_size == "340g"
    assert e.size_confirmed is True
    assert e.page_type == "product"


# ============================================================ 3-6: strictness
@pytest.mark.parametrize("query, title, slug, expect_reason", [
    # Wrong size (consumer electronics).
    ("Nimbus Tablet 256gb", "Nimbus Tablet 128gb", "nimbus-tablet-128gb", "different_size"),
    # Wrong variant (fitness).
    ("Apex Trainer", "Apex Trainer Pro", "apex-trainer-pro", "different_variant"),
    # Wrong flavour, expressed as a variant token.
    ("Ridgeline Roast Decaf", "Ridgeline Roast", "ridgeline-roast", "missing_identity_tokens"),
    # Multipack vs single unit (automotive parts).
    ("Torque Wiper Blade 6pack", "Torque Wiper Blade 1pack", "torque-wiper-blade-1pack", "different_size"),
])
def test_strict_identity_rejects_near_misses(service, query, title, slug, expect_reason):
    result, _ = run(service, query, site_rows={
        "rivertown.example": [organic(
            title, "https://rivertown.example/product/" + slug,
            title + " $19.99")]})

    assert result.products_found == 0, query + " wrongly matched " + title
    assert result.rejected_results, "the near miss must be reported, not dropped"
    assert result.rejected_results[0].reason == expect_reason


def test_harmless_normalisation_still_matches(service):
    """"Twelve" / "No." / "750 ML" must not block a genuine match."""
    result, _ = run(service, "Proper No. Twelve 750ml", site_rows={
        "rivertown.example": [organic(
            "Proper No 12 750 ML",
            "https://rivertown.example/product/proper-no-12-750ml",
            "Proper No 12 750 ML $29.99")]})
    assert result.products_found == 1
    assert result.evidence[0].price_status == "verified"


def test_a_contradiction_sets_not_found_rather_than_unknown(service):
    """A different size is a specific contradiction, unlike silence."""
    result, _ = run(service, "Nimbus Tablet 256gb", site_rows={
        "rivertown.example": [organic(
            "Nimbus Tablet 128gb",
            "https://rivertown.example/product/nimbus-tablet-128gb",
            "Nimbus Tablet 128gb $199.00")]})
    assert result.evidence[0].product_status == "not_found"
    assert result.products_not_found == 1


def test_silence_is_unknown_not_not_found(service):
    """Missing evidence is never proof of absence."""
    result, _ = run(service, "Widget 2000",
                    site_rows={"rivertown.example": []})
    assert result.evidence[0].product_status == "unknown"
    assert result.evidence[0].verification_reason == "insufficient_evidence"
    assert result.products_not_found == 0


# ============================================================ 7,8,9: evidence
def test_listing_page_cannot_verify_a_price(service):
    """A price on a filtered listing belongs to some product in the list."""
    result, _ = run(service, "Ridgeline Dark Roast 340g", site_rows={
        "rivertown.example": [organic(
            "Ridgeline Dark Roast 340g",
            "https://rivertown.example/collections/coffee?brand=ridgeline",
            "Ridgeline Dark Roast 340g $14.99")]}, market="Coffee")

    e = result.evidence[0]
    assert e.product_status == "found", "identity still holds"
    assert e.price_status == "unavailable"
    assert e.verification_reason == "price_not_product_specific"
    assert result.listing_pages_rejected == 1
    assert result.prices_verified == 0


def test_off_domain_rows_are_not_merchant_evidence(service):
    """A site: query that finds nothing falls back to the open web."""
    result, _ = run(service, "Widget 2000", site_rows={
        "rivertown.example": [organic(
            "Widget 2000", "https://elsewhere.example/product/widget-2000",
            "Widget 2000 $10.00")]})

    assert result.off_domain_rejected == 1
    assert result.products_found == 0
    assert result.evidence[0].product_status == "unknown"


def test_social_and_directory_merchants_never_reach_product_search(service, db):
    """Platform pages are rejected upstream, so they carry no product evidence."""
    result, _ = run(service, "Widget 2000", merchants=[
        local("Rivertown Supply", "https://www.instagram.com/rivertown", place_id="p1")])

    # The business is real, but a platform page is not its domain, so there is
    # no site to search.
    assert result.merchants_without_domain == 1
    assert result.merchants_searched == 0
    for merchant in db.query(Merchant).all():
        assert merchant.normalized_domain is None


def test_snippet_alone_cannot_establish_identity(service):
    """Identity comes from title and URL path; a snippet only corroborates."""
    result, _ = run(service, "Ridgeline Dark Roast 340g", site_rows={
        "rivertown.example": [organic(
            "Our Store",
            "https://rivertown.example/product/mystery-item",
            "We stock Ridgeline Dark Roast 340g $14.99")]}, market="Coffee")
    assert result.products_found == 0


# ============================================================ 10,11: merchants
def test_evidence_attaches_to_the_shared_merchant_identity(service, db):
    run(service, "Widget 2000", site_rows={
        "rivertown.example": [organic(
            "Widget 2000", "https://rivertown.example/product/widget-2000",
            "Widget 2000 $10.00")]})

    merchant = db.query(Merchant).filter(
        Merchant.normalized_domain == "rivertown.example").one()
    observation = db.query(ProductObservation).one()
    assert observation.merchant_id == merchant.id, \
        "products must reuse the merchants table, not a parallel identity"


def test_no_second_business_table_is_created():
    """Products attaches to merchants; it defines no business entity."""
    import inspect
    from app.models import product_observation

    source = inspect.getsource(product_observation)
    assert 'ForeignKey("merchants.id")' in source
    assert "__tablename__ = \"product_observations\"" in source


def test_uncertain_merchant_identity_carries_no_product_evidence(service, db):
    """Two stores of one chain: evidence cannot be attributed to either."""
    result, _ = run(service, "Widget 2000", merchants=[
        local("Chain Store", "https://chain.example", place_id="p1", address="1 A St"),
        local("Chain Store", "https://chain.example", place_id="p2", address="2 B St"),
    ], site_rows={"chain.example": [organic(
        "Widget 2000", "https://chain.example/product/widget-2000",
        "Widget 2000 $10.00")]})

    for e in result.evidence:
        assert e.price_status != "verified" or e.merchant_match_status == "matched"
    assert all(e.merchant_match_status != "uncertain" or e.price_status != "verified"
               for e in result.evidence)


# ============================================================ 12,13: provider
def test_provider_failure_is_not_product_not_found(service):
    """The failure that must never be silent."""
    result, _ = run(service, "Widget 2000", failing_sites={"rivertown.example"})

    assert result.merchant_provider_errors == 1
    assert stage(result, "product_evidence").status == "degraded"
    e = result.evidence[0]
    assert e.product_status == "unknown", "a failed lookup is not an absent product"
    assert e.verification_reason == "provider_request_failed"
    assert result.products_not_found == 0


def test_discovery_provider_failure_propagates(service):
    """If merchants cannot be discovered at all, that is not an empty result."""
    router = Router({}, {})
    with patch("app.services.api_budget.GoogleSearch") as MockSearch:
        MockSearch.return_value.get_dict.side_effect = RuntimeError("provider down")
        with pytest.raises(SerpApiProviderError):
            service.discover(product="Widget 2000", market="Coffee",
                             location="Austin, Texas")


def test_no_merchants_is_a_no_results_response(service):
    result, _ = run(service, "Widget 2000", merchants=[])
    assert result.provider_status == "no_results"
    assert result.evidence == []
    assert result.merchants_considered == 0


# ============================================================ 14,15: cache
def test_repeat_search_reuses_the_cache(service):
    rows = {"rivertown.example": [organic(
        "Widget 2000", "https://rivertown.example/product/widget-2000",
        "Widget 2000 $10.00")]}
    discovery = {"local_results": MERCHANT, "organic_results": []}
    router = Router(discovery, rows)
    with patch("app.services.api_budget.GoogleSearch", side_effect=router):
        service.discover(product="Widget 2000", market="Coffee",
                         location="Austin, Texas")
        first = len(router.queries)
        service.discover(product="Widget 2000", market="Coffee",
                         location="Austin, Texas")
        assert len(router.queries) == first, "a cache hit must spend nothing"


def test_a_different_product_does_not_reuse_another_products_evidence(service, db):
    """product A + merchant A must never serve product B + merchant A."""
    keys = []
    from app.services import api_budget as ab
    original = ab.ApiBudgetManager.execute_search

    def recording(self, cache_key, params, endpoint, domain=""):
        if endpoint == "merchant_website_indexed":
            keys.append(cache_key)
        return original(self, cache_key, params, endpoint, domain)

    with patch.object(ab.ApiBudgetManager, "execute_search", recording):
        run(service, "Widget 2000", site_rows={"rivertown.example": []})
        run(service, "Gadget 3000", site_rows={"rivertown.example": []})

    assert len(keys) == 2 and keys[0] != keys[1]
    assert "Widget 2000" in keys[0] and "Gadget 3000" in keys[1]


def test_a_different_merchant_does_not_reuse_another_merchants_evidence(service):
    keys = []
    from app.services import api_budget as ab
    original = ab.ApiBudgetManager.execute_search

    def recording(self, cache_key, params, endpoint, domain=""):
        if endpoint == "merchant_website_indexed":
            keys.append(cache_key)
        return original(self, cache_key, params, endpoint, domain)

    with patch.object(ab.ApiBudgetManager, "execute_search", recording):
        run(service, "Widget 2000", merchants=[
            local("A", "https://a.example", place_id="p1"),
            local("B", "https://b.example", place_id="p2")],
            site_rows={"a.example": [], "b.example": []})

    assert len(keys) == 2 and keys[0] != keys[1]
    assert "a.example" in keys[0] and "b.example" in keys[1]


def test_language_and_country_are_part_of_evidence_cache_identity(service):
    keys = []
    from app.services import api_budget as ab
    original = ab.ApiBudgetManager.execute_search

    def recording(self, cache_key, params, endpoint, domain=""):
        if endpoint == "merchant_website_indexed":
            keys.append(cache_key)
        return original(self, cache_key, params, endpoint, domain)

    with patch.object(ab.ApiBudgetManager, "execute_search", recording):
        run(service, "Widget 2000", site_rows={"rivertown.example": []})
        run(service, "Widget 2000", site_rows={"rivertown.example": []},
            hl="fr", gl="fr")

    assert len(keys) == 2 and keys[0] != keys[1]


# ============================================================ 16: history
def test_observations_accumulate_and_are_never_overwritten(service, db):
    rows = {"rivertown.example": [organic(
        "Widget 2000", "https://rivertown.example/product/widget-2000",
        "Widget 2000 $10.00")]}
    run(service, "Widget 2000", site_rows=rows)
    run(service, "Widget 2000", site_rows=rows, market="Hardware")

    observations = db.query(ProductObservation).all()
    assert len(observations) == 2, "history must accumulate"
    assert {o.market for o in observations} == {"Household Supplies", "Hardware"}
    # One business, many observations.
    assert db.query(Merchant).count() == 1


def test_saved_observations_can_be_listed_and_filtered(service, db):
    run(service, "Widget 2000", site_rows={"rivertown.example": [organic(
        "Widget 2000", "https://rivertown.example/product/widget-2000",
        "Widget 2000 $10.00")]}, market="Hardware")
    run(service, "Gadget 3000", site_rows={"rivertown.example": []},
        market="Electronics")

    total, records = service.list_saved()
    assert total == 2

    total, records = service.list_saved(product_query="widget 2000")
    assert total == 1 and records[0].product_name == "Widget 2000"

    total, _ = service.list_saved(market="Electronics")
    assert total == 1
    total, _ = service.list_saved(product_status="found")
    assert total == 1

    detail = service.get_saved(records[0].id)
    assert detail.merchant_name == "Rivertown Supply"
    assert detail.merchant_domain == "rivertown.example"
    assert service.get_saved(999999) is None


def test_listing_reads_the_database_without_a_provider(db):
    service = ProductService(db=db, competitor_service=None)
    total, records = service.list_saved()
    assert total == 0 and records == []


# ============================================================ 17,18: scope
def test_merchant_website_evidence_is_catalog_scope(service, db):
    """A catalogue page proves the merchant offers it, not that a store holds it."""
    result, _ = run(service, "Widget 2000", site_rows={
        "rivertown.example": [organic(
            "Widget 2000", "https://rivertown.example/product/widget-2000",
            "Widget 2000 $10.00 in stock")]})

    e = result.evidence[0]
    assert e.evidence_scope == "catalog"
    assert e.inventory_confirmed is False

    observation = db.query(ProductObservation).one()
    assert observation.evidence_scope == "catalog"
    assert bool(observation.inventory_confirmed) is False


def test_an_in_stock_snippet_does_not_confirm_store_inventory(service):
    """"In stock" on a catalogue page is still not a physical shelf."""
    result, _ = run(service, "Widget 2000", site_rows={
        "rivertown.example": [organic(
            "Widget 2000", "https://rivertown.example/product/widget-2000",
            "Widget 2000 $10.00 add to cart in stock available")]})
    assert result.evidence[0].inventory_confirmed is False


def test_unverifiable_size_keeps_the_product_but_drops_the_price(service):
    """Identity can hold while the requested size is unconfirmed."""
    result, _ = run(service, "Widget 2000 750ml", site_rows={
        "rivertown.example": [organic(
            "Widget 2000", "https://rivertown.example/product/widget-2000",
            "Widget 2000 $10.00")]})

    e = result.evidence[0]
    assert e.product_status == "found"
    assert e.price_status == "unavailable"
    assert e.verification_reason == "size_unverified"


@pytest.mark.parametrize("snippet, reason", [
    ("Widget 2000 $10.00 - $20.00", "price_range"),
    ("Widget 2000 starting at $10.00", "ambiguous_price"),
    ("Widget 2000 available now", "price_unavailable"),
])
def test_unreliable_prices_are_never_verified(service, snippet, reason):
    result, _ = run(service, "Widget 2000", site_rows={
        "rivertown.example": [organic(
            "Widget 2000", "https://rivertown.example/product/widget-2000",
            snippet)]})
    e = result.evidence[0]
    assert e.product_status == "found"
    assert e.price_status == "unavailable"
    assert e.verification_reason == reason
    assert e.price is None


# ============================================================ generic design
def test_module_names_no_industry_product_or_place():
    import ast
    import inspect
    from app.services import product_service

    tree = ast.parse(inspect.getsource(product_service))
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef)):
            body = getattr(node, "body", None)
            if body and isinstance(body[0], ast.Expr) and \
                    isinstance(body[0].value, ast.Constant) and \
                    isinstance(body[0].value.value, str):
                docstrings.add(id(body[0].value))
    literals = " ".join(n.value.lower() for n in ast.walk(tree)
                        if isinstance(n, ast.Constant)
                        and isinstance(n.value, str) and id(n) not in docstrings)

    for forbidden in ("wine", "liquor", "coffee", "total wine", "new jersey",
                      "holmdel", "secaucus", "austin"):
        assert forbidden not in literals, forbidden + " is hardcoded"


def test_credit_spend_is_bounded_by_merchant_count(service):
    """A broad market must not quietly spend one credit per merchant found."""
    merchants = [local("M" + str(i), "https://m" + str(i) + ".example",
                       place_id="p" + str(i)) for i in range(10)]
    result, router = run(service, "Widget 2000", merchants=merchants,
                         site_rows={}, max_merchants=3)

    assert result.merchants_considered == 10
    assert result.merchants_searched == 3
    assert len([q for q in router.queries if q.startswith("site:")]) == 3
    assert stage(result, "merchant_selection").status == "degraded"
