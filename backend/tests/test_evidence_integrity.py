"""Evidence-integrity regression tests.

Covers the scenarios listed in the project spec's testing requirements.
Every case is industry-generic; the wine examples are regression fixtures
only and carry no special production logic.
"""
import pytest

from app.providers.merchant_website_provider import (
    MerchantWebsitePriceProvider, classify_page_type,
)
from app.services.merchant_identity import (
    host_matches_domain, match_merchant, normalize_domain, normalize_name,
)
from app.services.product_identity import canonicalise, extract_sizes, match_product


# ---------------------------------------------------------------- normalisation
@pytest.mark.parametrize("a,b", [
    ("750 ML", "750ml"),
    ("15 Yr", "15 Year"),
    ("15 Year Old", "15 Yr"),
    ("Proper No. 12", "Proper No Twelve"),
    ("A & B", "A and B"),
])
def test_harmless_differences_normalise_together(a, b):
    assert canonicalise(a) == canonicalise(b)


@pytest.mark.parametrize("query,candidate", [
    ("Samsung Galaxy S25 256GB", "Samsung Galaxy S25 128GB"),
    ("iPhone 15 Pro", "iPhone 15 Pro Max"),
    ("Apple Watch GPS", "Apple Watch Cellular"),
    ("Dalmore 15", "Dalmore 12"),
    ("Product A 750ml", "Product A 1L"),
])
def test_meaningful_attributes_stay_different(query, candidate):
    assert not match_product(query, candidate)["matched"]


def test_size_parsing_is_deterministic():
    assert extract_sizes("Proper No. Twelve 50ML 4-Pack") == ["50ml", "4pack"]


# ---------------------------------------------------------------- recall
@pytest.mark.parametrize("candidate", [
    "Proper No. Twelve Irish Apple Flavored Whiskey",
    "Proper Twelve Apple Irish Whiskey",
    "Proper No Twelve Irish Apple Whiskey",
])
def test_controlled_normalisation_improves_recall(candidate):
    """Naming variants of one product must resolve together (spec 39)."""
    assert match_product("Proper No. 12 Irish Apple Whiskey", candidate)["matched"]


def test_vintage_or_sku_does_not_block_recall():
    assert match_product("Josh Cellars Cabernet Sauvignon",
                         "Josh Cellars Cabernet Sauvignon 2021")["matched"]


# ---------------------------------------------------------------- identity source
def test_snippet_cannot_establish_product_identity():
    """A category page whose snippet mentions the product is not the product."""
    r = match_product("Proper No. 12 Irish Apple Whiskey",
                      "Irish Whiskey - Super Buy Rite",
                      snippet="Proper No. Twelve apple whiskey in stock $32.95")
    assert not r["matched"]
    assert r["reason"] == "missing_identity_tokens"


def test_brand_listing_title_is_not_the_product():
    assert not match_product("Proper No. 12 Irish Apple Whiskey",
                             "Proper No. Twelve")["matched"]


def test_url_slug_may_establish_identity():
    r = match_product("Proper No. 12 Irish Apple Whiskey", "",
                      url="https://x.com/shop/product/proper-no-twelve-irish-apple-whiskey/1")
    assert r["matched"]


# ---------------------------------------------------------------- size gate
def test_requested_size_unconfirmed_blocks_price_not_product():
    """Spec 23/52: product evidence survives, only the price is blocked."""
    r = match_product("Product A 4-pack", "Product A single unit")
    assert r["matched"] is True
    assert r["size_confirmed"] is False


def test_requested_size_confirmed():
    r = match_product("Product A 750ml", "Product A 750 ML bottle")
    assert r["matched"] and r["size_confirmed"] and r["observed_size"] == "750ml"


def test_unsized_request_records_observed_size():
    r = match_product("Dalmore 15 Yr Malt", "Dalmore 15 Yr Malt",
                      snippet="Wine Outlet 750ML $139.99 Add to Cart")
    assert r["matched"] and r["size_confirmed"] and r["observed_size"] == "750ml"


# ---------------------------------------------------------------- page type
@pytest.mark.parametrize("url,expected", [
    ("https://x.com/shop/product/some-item/123", "product"),
    ("https://x.com/products/widget-2000", "product"),
    ("https://x.com/shop/?brands=Some+Brand", "listing"),
    ("https://x.com/shop/?subtype=irish+whiskey", "listing"),
    ("https://x.com/collections/all", "listing"),
    ("https://x.com/category/whiskey/irish", "listing"),
    ("https://x.com/about-us", "unknown"),
])
def test_page_type_classification(url, expected):
    assert classify_page_type(url) == expected


# ---------------------------------------------------------------- provenance
def test_off_domain_results_are_not_merchant_evidence():
    """A site: query with no hits falls back to the open web (spec 20)."""
    assert not host_matches_domain("https://youtube.com/watch?v=x", "example.com")
    assert host_matches_domain("https://shop.example.com/p/1", "example.com")
    assert host_matches_domain("https://www.example.com/p/1", "example.com")


class _StubBudget:
    def __init__(self, payload):
        self.payload = payload

    def execute_search(self, cache_key, params, endpoint, domain=""):
        return self.payload


def test_provider_rejects_off_domain_rows():
    payload = {"organic_results": [
        {"title": "NO (Official Video)", "link": "https://youtube.com/watch?v=1", "snippet": ""},
        {"title": "Widget 2000", "link": "https://example.com/products/widget-2000",
         "snippet": "$19.99 Add to Cart"},
    ]}
    out = MerchantWebsitePriceProvider().discover_prices(
        {"domain": "example.com"}, "Widget 2000", _StubBudget(payload))
    assert out["status"] == "ok"
    assert out["rows_returned"] == 2
    assert out["off_domain_rejected"] == 1
    assert len(out["observations"]) == 1
    assert out["observations"][0]["page_type"] == "product"


def test_provider_reports_error_rather_than_empty():
    out = MerchantWebsitePriceProvider().discover_prices(
        {"domain": "example.com"}, "Widget", _StubBudget(None))
    assert out["status"] == "error"
    assert out["observations"] == []


def test_provider_skips_merchant_without_domain():
    out = MerchantWebsitePriceProvider().discover_prices(
        {"domain": ""}, "Widget", _StubBudget({}))
    assert out["status"] == "skipped"


# ---------------------------------------------------------------- price extraction
@pytest.mark.parametrize("snippet", [
    "Starting at $39.99",
    "From $39.99",
    "$29.99 - $49.99",
    "Contact for price",
])
def test_unreliable_prices_are_not_extracted(snippet):
    info = MerchantWebsitePriceProvider().extract_price_info("Widget 2000", snippet, "Widget 2000")
    assert info["price"] is None


def test_clear_price_is_extracted():
    info = MerchantWebsitePriceProvider().extract_price_info(
        "Widget 2000", "Widget 2000 750ML $39.99 Add to Cart", "Widget 2000")
    assert info["price"] == 39.99


def test_multiple_unrelated_prices_are_ambiguous():
    info = MerchantWebsitePriceProvider().extract_price_info(
        "Brand page", "Widget A $19.99 Widget B $29.99 Widget C $39.99", "Widget A")
    assert info["price"] is None or info["ambiguous_price"] or info["price"] == 19.99


# ---------------------------------------------------------------- merchant identity
def _merchants():
    return [
        {"name": "Weak Fuzzy Liquors", "normalized_name": normalize_name("Weak Fuzzy Liquors"),
         "domain": "weakfuzzy.com", "address": "1 A St"},
        {"name": "Buy Rite Wines", "normalized_name": normalize_name("Buy Rite Wines"),
         "domain": "buyritewines.com", "address": "2 B St"},
    ]


def test_exact_domain_beats_earlier_weak_candidate():
    """Spec 24 is a ranked hierarchy, not first-merchant-wins."""
    r = match_merchant("buyritewines.com", "Buy Rite Wines", _merchants())
    assert r["method"] == "exact_domain"
    assert r["status"] == "matched"
    assert r["merchant"]["name"] == "Buy Rite Wines"


def test_chain_domain_across_several_stores_is_uncertain():
    chain = [
        {"name": "Chain A", "normalized_name": "chaina", "domain": "chain.com", "address": "x"},
        {"name": "Chain B", "normalized_name": "chainb", "domain": "chain.com", "address": "y"},
    ]
    r = match_merchant("chain.com", "Chain", chain)
    assert r["status"] == "uncertain"
    assert r["merchant"] is None


def test_fuzzy_match_is_never_high_confidence():
    r = match_merchant("", "Jersey City Super Buy Rite",
                       [{"name": "Super Buy Rite", "normalized_name": "superbuyrite",
                         "domain": "", "address": ""}])
    assert r["method"] == "fuzzy_name"
    assert r["confidence"] == "low"
    assert r["status"] == "uncertain"


def test_short_names_cannot_fuzzy_match():
    r = match_merchant("", "Wine", [{"name": "Wine Outlet", "normalized_name": "wineoutlet",
                                     "domain": "", "address": ""}])
    assert r["status"] == "unmatched"


def test_unmatched_when_nothing_resembles():
    r = match_merchant("unrelated.com", "Unrelated Shop", _merchants())
    assert r["status"] == "unmatched"


def test_domain_normalisation():
    assert normalize_domain("https://www.Example.com/path") == "example.com"
    assert normalize_domain("example.com") == "example.com"
    assert normalize_domain("") == ""


def test_exact_name_matches_when_no_domain_is_available():
    """Tier 2: a shopping source with no usable link still has a name."""
    r = match_merchant("", "Buy Rite Wines", _merchants())
    assert r["method"] == "exact_name"
    assert r["status"] == "matched"
    assert r["merchant"]["domain"] == "buyritewines.com"


def test_ambiguous_chain_name_stays_uncertain_even_with_an_address():
    """Documents the current, deliberately conservative outcome.

    The spec's tier 3 (name + address) is ranked below tier 2 (exact name), and
    tier 3's condition is tier 2's condition plus an address check -- so an
    ambiguous exact-name match returns "uncertain" before tier 3 is ever
    consulted, and tier 3 is unreachable. The safe half of that is what matters
    here and is what this test pins: a chain whose physical store cannot be
    identified is never treated as identified. Making tier 3 reachable would
    turn some of these into verified store-level prices, which is a change to
    price attribution and not something to do silently.
    """
    chain = [
        {"name": "Chain", "normalized_name": normalize_name("Chain"),
         "domain": "", "address": "100 First Avenue, Springfield"},
        {"name": "Chain", "normalized_name": normalize_name("Chain"),
         "domain": "", "address": "900 Ninth Street, Shelbyville"},
    ]
    assert match_merchant("", "Chain", chain)["status"] == "uncertain"

    with_address = match_merchant("", "Chain", chain,
                                  source_address="900 Ninth Street")
    assert with_address["status"] == "uncertain"
    assert with_address["merchant"] is None


def test_name_and_address_tier_is_currently_unreachable():
    """Guards the finding above so a future change to it is deliberate."""
    from app.services.merchant_identity import TIERS

    methods = [t[0] for t in TIERS]
    assert methods.index("exact_name") < methods.index("name_and_address"), (
        "tier order changed; if name_and_address now precedes exact_name, the "
        "ambiguous-chain test above needs revisiting")


def test_fuzzy_name_never_outranks_an_exact_domain_elsewhere_in_the_list():
    """A weaker tier must not win merely by appearing first."""
    merchants = [
        {"name": "Buy Rite Wines Annex", "normalized_name": normalize_name("Buy Rite Wines Annex"),
         "domain": "", "address": "9 Z St"},
        {"name": "Buy Rite Wines", "normalized_name": normalize_name("Buy Rite Wines"),
         "domain": "buyritewines.com", "address": "2 B St"},
    ]
    r = match_merchant("buyritewines.com", "Buy Rite Wines", merchants)
    assert r["method"] == "exact_domain"
    assert r["merchant"]["domain"] == "buyritewines.com"
