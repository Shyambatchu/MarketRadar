"""Not every search result is a competitor.

A market search returns the businesses themselves mixed with directories that
list them, articles about them, marketplaces reselling them and social
profiles. Only the first kind is a competitor.

Test markets here are deliberately varied and generic -- coffee shops,
automotive repair, fitness centres -- so nothing can quietly become specific to
one industry.
"""
import pytest

from app.services.result_classifier import (
    ARTICLE, BUSINESS, DIRECTORY, MARKETPLACE, SOCIAL, UNKNOWN,
    classify_local_result, classify_organic_result, classify_organic_results,
    registrable_domain,
)


# ------------------------------------------------------------------ domains
@pytest.mark.parametrize("value, expected", [
    ("https://www.example.com/path", "example.com"),
    ("m.yelp.com", "yelp.com"),
    ("https://a.b.example.com/", "example.com"),
    ("https://shop.example.co.uk/x", "example.co.uk"),
    ("https://www.example.com.au", "example.com.au"),
    ("example.de", "example.de"),
])
def test_registrable_domain(value, expected):
    assert registrable_domain(value) == expected


# ------------------------------------------------------------------ local
def test_structured_local_result_is_a_business():
    """Local results are why local discovery is the stronger source."""
    c = classify_local_result({"title": "Bean & Brew", "address": "1 Main St",
                               "place_id": "abc"})
    assert c.entity_type == BUSINESS
    assert c.confidence == "high"
    assert c.is_competitor_candidate


def test_local_result_with_address_but_no_place_id_is_still_a_business():
    c = classify_local_result({"title": "City Auto Repair", "address": "9 Elm Rd"})
    assert c.entity_type == BUSINESS


def test_local_result_without_any_identity_is_unknown():
    """Nothing to identify it with means it is not usable evidence."""
    c = classify_local_result({"title": "Something"})
    assert c.entity_type == UNKNOWN
    assert not c.is_competitor_candidate


# ------------------------------------------------------------------ organic
@pytest.mark.parametrize("title, url, expected", [
    # The business's own site.
    ("Bean & Brew Coffee", "https://beanandbrew.com/", BUSINESS),
    ("City Auto Repair - Services", "https://cityautorepair.com/services", BUSINESS),
    ("Iron Works Fitness", "https://ironworksfitness.de/", BUSINESS),
    # Review directories and aggregators.
    ("TOP 10 BEST Coffee Shops near Austin", "https://m.yelp.com/search?q=coffee", DIRECTORY),
    ("Best Gyms in Leeds - 2026", "https://www.showmelocal.com/leeds/gyms", DIRECTORY),
    ("Acme Auto | Better Business Bureau", "https://www.bbb.org/us/acme-auto", DIRECTORY),
    # Social profiles.
    ("Bean & Brew | Facebook", "https://www.facebook.com/beanandbrew", SOCIAL),
    ("Iron Works Fitness (@ironworks)", "https://www.instagram.com/ironworks", SOCIAL),
    # Marketplaces.
    ("Espresso Machine", "https://www.amazon.com/dp/B0123", MARKETPLACE),
    ("Order from City Diner", "https://www.ubereats.com/store/city-diner", MARKETPLACE),
    # Editorial.
    ("The 12 best coffee shops in Austin", "https://www.timeout.com/austin/coffee", ARTICLE),
    ("Our favourite garages", "https://someblog.com/blog/2026/03/garages", ARTICLE),
    ("Top 5 Gyms You Should Try", "https://randomsite.com/fitness", ARTICLE),
])
def test_organic_classification(title, url, expected):
    assert classify_organic_result(title, url).entity_type == expected


def test_listing_path_on_an_unknown_site_reads_as_a_directory():
    """A business does not file itself under /biz/<someone>."""
    c = classify_organic_result("Acme Repair",
                                "https://somesite.com/biz/acme-repair")
    assert c.entity_type == DIRECTORY
    assert c.reason == "listing_path_segment"


def test_deep_unrecognised_path_is_unknown_not_a_business():
    """Absence of a signal is not evidence of a business."""
    c = classify_organic_result("Page", "https://example.com/a/b/c/d/e")
    assert c.entity_type == UNKNOWN
    assert not c.is_competitor_candidate


def test_local_discovery_corroboration_overrides_heuristics():
    """A second independent source beats every guess in the module."""
    url = "https://somesite.com/a/b/c/d/e"
    assert classify_organic_result("X", url).entity_type == UNKNOWN
    c = classify_organic_result("X", url,
                                known_business_domains={"somesite.com"})
    assert c.entity_type == BUSINESS
    assert c.confidence == "high"
    assert c.reason == "corroborated_by_local_discovery"


def test_own_domain_signal_is_never_high_confidence():
    """The weakest positive signal must not masquerade as strong evidence."""
    c = classify_organic_result("Bean & Brew", "https://beanandbrew.com/")
    assert c.entity_type == BUSINESS
    assert c.confidence == "medium"


def test_missing_url_cannot_be_classified_as_a_business():
    assert classify_organic_result("Bean & Brew", "").entity_type == UNKNOWN


def test_classification_retains_every_result():
    """Rejected results are reported, not silently dropped."""
    rows = [
        {"title": "Bean & Brew", "link": "https://beanandbrew.com/"},
        {"title": "Best 10 cafes", "link": "https://m.yelp.com/search"},
    ]
    out = classify_organic_results(rows)
    assert len(out) == 2
    assert [o["classification"].entity_type for o in out] == [BUSINESS, DIRECTORY]


def _code_string_constants(module):
    """Every string literal in a module except its docstrings.

    Prose may name an industry to say the code does not depend on it; the code
    itself may not. Only the latter is the invariant worth testing.
    """
    import ast
    import inspect

    tree = ast.parse(inspect.getsource(module))
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                             ast.AsyncFunctionDef)):
            body = getattr(node, "body", None)
            if body and isinstance(body[0], ast.Expr) and \
                    isinstance(body[0].value, ast.Constant) and \
                    isinstance(body[0].value.value, str):
                docstrings.add(id(body[0].value))

    return [n.value.lower() for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
            and id(n) not in docstrings]


def test_classifier_code_names_no_industry_or_place():
    """The classifier must stay industry- and location-agnostic.

    Platform domains are allowed: a social network or review directory is
    internet infrastructure, the same whatever the market. An industry term or
    a place name would not be.
    """
    from app.services import result_classifier

    haystack = " ".join(_code_string_constants(result_classifier))
    for forbidden in ("wine", "liquor", "coffee", "fitness", "automotive",
                      "restaurant", "new jersey", "secaucus", "holmdel",
                      "austin", "texas"):
        assert forbidden not in haystack, \
            forbidden + " is hardcoded in the classifier"


def test_competitor_service_code_names_no_industry_or_place():
    from app.services import competitor_service

    haystack = " ".join(_code_string_constants(competitor_service))
    for forbidden in ("wine", "liquor", "coffee", "fitness", "automotive",
                      "new jersey", "secaucus", "holmdel", "austin"):
        assert forbidden not in haystack, \
            forbidden + " is hardcoded in the competitor service"


# ------------------------------------------------------------ live findings
@pytest.mark.parametrize("title, url", [
    # Observed live: a Q&A page was recorded as a competitor because its
    # shallow path read as a business homepage.
    ("What are great wine shops in New York City and why?",
     "https://www.quora.com/What-are-great-wine-shops-in-New-York-City-and-why"),
    ("Which gym should I join?", "https://www.quora.com/Which-gym-should-I-join"),
])
def test_qa_community_pages_are_not_businesses(title, url):
    c = classify_organic_result(title, url)
    assert c.entity_type != BUSINESS
    assert not c.is_competitor_candidate


@pytest.mark.parametrize("title", [
    "What are great coffee shops nearby?",
    "How do I find a good mechanic?",
    "Any recommendations for a gym?",
])
def test_question_titles_are_content_not_companies(title):
    """A business is not named as a question."""
    c = classify_organic_result(title, "https://unknownsite.com/some-page")
    assert c.entity_type == ARTICLE
    assert c.reason == "question_title"


def test_a_business_name_containing_punctuation_still_classifies(title=None):
    """The question rule must not swallow ordinary business names."""
    for name in ("Bean & Brew Coffee", "Smith's Auto Repair",
                 "Iron Works Fitness - Home"):
        c = classify_organic_result(name, "https://example-business.com/")
        assert c.entity_type == BUSINESS, name


def test_platform_domains_are_rejected_as_business_identity():
    from app.services.result_classifier import is_platform_domain

    for url in ("https://www.instagram.com/somebusiness",
                "https://www.quora.com/Some-Question",
                "https://m.yelp.com/biz/x", "https://facebook.com/x"):
        assert is_platform_domain(url), url
    for url in ("https://addonsautomotive.in/", "https://wineoutlet.com/",
                "https://hazletbuyrite.com/"):
        assert not is_platform_domain(url), url
