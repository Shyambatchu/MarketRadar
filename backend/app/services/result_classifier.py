"""What kind of web entity is this search result?

Competitor discovery must not treat every search result as a competitor. A
search for businesses in a market returns a mixture of the businesses
themselves, directories that list them, articles about them, marketplaces that
resell them, and social profiles. Only the first kind is a competitor; the rest
are pages *about* competitors, and recording them would fill the module with
entities that are not businesses at all.

Everything here classifies the *shape of a web property*, never an industry, a
product category or a named competitor. The platform sets below name kinds of
internet infrastructure -- social networks, marketplaces, review directories --
which are the same regardless of whether the market is coffee shops, automotive
repair or fitness centres. Nothing in this module refers to any specific
market.

Structured local/Maps results skip this entirely: a result carrying a place id,
an address and coordinates is a physical business by construction, which is why
local discovery is the stronger source.
"""
import re
from typing import Dict, List, Optional
from urllib.parse import urlparse

from app.services.merchant_identity import normalize_domain

# ---------------------------------------------------------------------------
# Entity types
# ---------------------------------------------------------------------------
BUSINESS = "business"
DIRECTORY = "directory"
SOCIAL = "social"
ARTICLE = "article"
MARKETPLACE = "marketplace"
UNKNOWN = "unknown"

# Only a business may become a competitor.
COMPETITOR_ELIGIBLE = {BUSINESS}

# ---------------------------------------------------------------------------
# Platform taxonomy -- kinds of internet infrastructure, not industries.
# Matched on registrable domain, so regional variants (example.co.uk) match too.
# ---------------------------------------------------------------------------
SOCIAL_PLATFORMS = {
    "facebook.com", "instagram.com", "twitter.com", "x.com", "linkedin.com",
    "tiktok.com", "youtube.com", "pinterest.com", "reddit.com", "tumblr.com",
    "threads.net", "snapchat.com", "vk.com", "weibo.com", "nextdoor.com",
    # Q&A and community sites: user-generated pages *about* businesses, whose
    # URLs look like a shallow own-domain path and so would otherwise read as
    # a business homepage.
    "quora.com", "stackexchange.com", "stackoverflow.com", "answers.com",
    "discourse.org", "producthunt.com", "trustradius.com",
}

# Directories and review aggregators: they list many businesses, so a page on
# one of them describes a business but is not that business's own presence.
DIRECTORY_PLATFORMS = {
    "yelp.com", "yellowpages.com", "yp.com", "bbb.org", "manta.com",
    "tripadvisor.com", "foursquare.com", "mapquest.com", "superpages.com",
    "citysearch.com", "angi.com", "angieslist.com", "thumbtack.com",
    "houzz.com", "trustpilot.com", "glassdoor.com", "indeed.com",
    "crunchbase.com", "zoominfo.com", "dnb.com", "chamberofcommerce.com",
    "showmelocal.com", "hotfrog.com", "brownbook.net", "cylex.us.com",
    "birdeye.com", "wikipedia.org", "wikidata.org",
}

MARKETPLACE_PLATFORMS = {
    "amazon.com", "ebay.com", "etsy.com", "walmart.com", "alibaba.com",
    "aliexpress.com", "wish.com", "temu.com", "mercadolibre.com",
    "doordash.com", "ubereats.com", "grubhub.com", "instacart.com",
    "postmates.com", "seamless.com", "shipt.com", "gopuff.com",
}

# Publishers and content platforms.
ARTICLE_PLATFORMS = {
    "medium.com", "substack.com", "blogspot.com", "wordpress.com",
    "wixsite.com", "forbes.com", "businessinsider.com", "nytimes.com",
    "theguardian.com", "cnn.com", "bbc.com", "reuters.com", "bloomberg.com",
    "eater.com", "timeout.com", "thrillist.com",
}

# ---------------------------------------------------------------------------
# Structural signals, independent of any platform list
# ---------------------------------------------------------------------------

# "Top 10 ...", "Best ... near me", "5 Great ..." -- a page about many
# businesses, so it identifies none of them.
_LISTICLE_TITLE = re.compile(
    r"\b(?:top|best|cheapest|greatest)\b\s*\d*\s|"
    r"^\s*\d+\s+(?:best|top|great|amazing)\b|"
    r"\b\d+\s+(?:best|top)\b",
    re.IGNORECASE)

# "... near <place>", "... in <place> - 2026" reads as a roundup, not a shop.
_ROUNDUP_TITLE = re.compile(r"\bnear\s+(?:me|you)\b|\bguide\s+to\b|"
                            r"\bthings\s+to\s+do\b|\bwhere\s+to\b",
                            re.IGNORECASE)

# A dated path is editorial: /2026/03/..., /news/2026-03-01-...
_DATED_PATH = re.compile(r"/(?:19|20)\d{2}(?:[/-]\d{1,2})")

# A question is content, never a company. Businesses are not named
# "What are great wine shops in New York City and why?" -- observed live, on a
# Q&A page whose shallow path would otherwise read as a business homepage.
_QUESTION_TITLE = re.compile(
    r"\?\s*$|"
    r"^\s*(?:what|why|how|who|where|when|which|is|are|do|does|did|can|should|"
    r"would|could|any)\b[^.]*\?",
    re.IGNORECASE)

_ARTICLE_PATH_SEGMENTS = {
    "blog", "blogs", "news", "article", "articles", "story", "stories",
    "press", "post", "posts", "magazine", "guide", "guides", "review",
    "reviews", "insights", "resources",
}

# Path segments a directory uses to scope one of its many listings.
_DIRECTORY_PATH_SEGMENTS = {
    "biz", "listing", "listings", "directory", "directories", "profile",
    "profiles", "company", "companies", "business", "businesses", "place",
    "places", "store-locator", "locations",
}


# Suffixes reserved for government and military bodies. Such a site is not a
# commercial business competing in a market, whatever shape its URL takes.
# This is a property of the namespace, not of any industry, so it holds for
# every market in every country.
_NON_COMMERCIAL_SUFFIXES = {"gov", "mil"}


def is_non_commercial_domain(url_or_domain: str) -> bool:
    """True for a government or military namespace.

    Observed: an unscoped search matched a government space-weather page whose
    path happened to look like a business homepage, and it was persisted as a
    competitor. The URL shape was genuinely indistinguishable; the namespace
    was not.
    """
    # The full host, not the registrable domain: reducing "defence.mil.au" to
    # "mil.au" would drop the very label being tested for.
    host = normalize_domain(url_or_domain) if ("/" in url_or_domain
                                               or url_or_domain.startswith("http")) \
        else (url_or_domain or "").lower().split(":")[0]
    if host.startswith("www."):
        host = host[4:]
    labels = [label for label in host.split(".") if label]
    if not labels:
        return False
    if labels[-1] in _NON_COMMERCIAL_SUFFIXES:
        return True
    # gov.uk, mil.au -- a reserved label under a country code. Guarded on the
    # country code so an ordinary domain like "mil.com" is unaffected.
    # Two labels suffice: "www.gov.uk" reduces to "gov.uk" itself.
    return (len(labels) >= 2 and labels[-2] in _NON_COMMERCIAL_SUFFIXES
            and len(labels[-1]) == 2)


def registrable_domain(url_or_domain: str) -> str:
    """Best-effort registrable domain, for matching platform sets.

    Deliberately simple: the last two labels, plus a third for the common
    two-part public suffixes. Good enough to recognise a platform, and it
    never has to be exactly right for correctness -- a miss just leaves the
    result to the structural signals below.
    """
    domain = normalize_domain(url_or_domain) if "/" in url_or_domain or \
        url_or_domain.startswith("http") else (url_or_domain or "").lower()
    domain = domain.split(":")[0]
    if domain.startswith("www."):
        domain = domain[4:]
    labels = [label for label in domain.split(".") if label]
    if len(labels) <= 2:
        return ".".join(labels)
    # co.uk, com.au, co.jp, com.br ...
    if labels[-2] in {"co", "com", "net", "org", "gov", "edu", "ac"} and \
            len(labels[-1]) == 2:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


#: Every platform domain, for rejecting one as a business's own identity.
PLATFORM_DOMAINS = (SOCIAL_PLATFORMS | DIRECTORY_PLATFORMS
                    | MARKETPLACE_PLATFORMS | ARTICLE_PLATFORMS)


def is_platform_domain(url_or_domain: str) -> bool:
    """True when this domain belongs to a platform rather than one business.

    Small businesses often list a social or marketplace page as their website.
    That page is evidence the business exists, but the domain is not *theirs*:
    treating it as their identity would attribute the platform to them and --
    far worse -- make every business sharing that platform collide on the
    exact-domain tier and be merged into one record.
    """
    if not url_or_domain:
        return False
    return registrable_domain(url_or_domain) in PLATFORM_DOMAINS


class Classification:
    def __init__(self, entity_type: str, confidence: str, reason: str):
        self.entity_type = entity_type
        self.confidence = confidence  # high | medium | low
        self.reason = reason

    @property
    def is_competitor_candidate(self) -> bool:
        return self.entity_type in COMPETITOR_ELIGIBLE

    def as_dict(self) -> Dict:
        return {"entity_type": self.entity_type, "confidence": self.confidence,
                "reason": self.reason}

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return "Classification(%s, %s, %s)" % (
            self.entity_type, self.confidence, self.reason)


def classify_local_result(result: Dict) -> Classification:
    """A Maps/local result is a physical business by construction.

    It is only downgraded when the provider gave us nothing to identify it
    with -- no place id and no address.
    """
    website = result.get("website") or ""
    if website and is_non_commercial_domain(website):
        # A government office listed on Maps is a place, not a competitor.
        return Classification(UNKNOWN, "high", "non_commercial_domain")
    has_place = bool(result.get("place_id"))
    has_address = bool(result.get("address"))
    if has_place or has_address:
        return Classification(BUSINESS, "high", "structured_local_result")
    return Classification(UNKNOWN, "low", "local_result_without_identity")


def classify_organic_result(title: str, url: str, snippet: str = "",
                            known_business_domains: Optional[set] = None) -> Classification:
    """Classify one organic result.

    ``known_business_domains`` are domains already confirmed as businesses by
    local discovery. A match there is the strongest signal available, because a
    second independent source agrees the domain belongs to a real business --
    and it overrides the structural heuristics, which exist only to guess at
    what the local source already told us.
    """
    title = title or ""
    url = url or ""
    snippet = snippet or ""

    if not url:
        return Classification(UNKNOWN, "low", "no_url")

    domain = registrable_domain(url)
    if not domain:
        return Classification(UNKNOWN, "low", "unparseable_url")

    # A government or military namespace is decisive: whatever the page is, it
    # is not a business competing in a market. Tested on the full host --
    # the registrable domain of "www.gov.uk" is "gov.uk", which drops the
    # country-code context the test needs.
    if is_non_commercial_domain(url):
        return Classification(UNKNOWN, "high", "non_commercial_domain")

    # Cross-source corroboration beats every heuristic below.
    if known_business_domains and domain in known_business_domains:
        return Classification(BUSINESS, "high", "corroborated_by_local_discovery")

    # Platform identity is decisive: a page hosted by a directory is the
    # directory's page, whatever its title says.
    if domain in SOCIAL_PLATFORMS:
        return Classification(SOCIAL, "high", "social_platform")
    if domain in DIRECTORY_PLATFORMS:
        return Classification(DIRECTORY, "high", "directory_platform")
    if domain in MARKETPLACE_PLATFORMS:
        return Classification(MARKETPLACE, "high", "marketplace_platform")
    if domain in ARTICLE_PLATFORMS:
        return Classification(ARTICLE, "high", "publisher_platform")

    path = (urlparse(url).path or "").lower()
    segments = [s for s in path.split("/") if s]

    # A roundup or listicle covers many businesses, so it identifies none.
    if _LISTICLE_TITLE.search(title) or _ROUNDUP_TITLE.search(title):
        return Classification(ARTICLE, "medium", "listicle_or_roundup_title")

    if _QUESTION_TITLE.search(title):
        return Classification(ARTICLE, "medium", "question_title")

    if _DATED_PATH.search(path):
        return Classification(ARTICLE, "medium", "dated_url_path")

    if any(seg in _ARTICLE_PATH_SEGMENTS for seg in segments):
        return Classification(ARTICLE, "medium", "editorial_path_segment")

    # A per-listing path on a site we do not otherwise recognise still reads
    # as a directory: a business does not file itself under /biz/<someone>.
    if any(seg in _DIRECTORY_PATH_SEGMENTS for seg in segments):
        return Classification(DIRECTORY, "medium", "listing_path_segment")

    # A site's own root or a shallow path is the ordinary shape of a business
    # homepage. This is the weakest positive signal in the module, so it is
    # reported as medium and never as high.
    if len(segments) <= 2:
        return Classification(BUSINESS, "medium", "own_domain_shallow_path")

    return Classification(UNKNOWN, "low", "no_decisive_signal")


def classify_organic_results(results: List[Dict],
                             known_business_domains: Optional[set] = None) -> List[Dict]:
    """Annotate each result with its classification, dropping nothing.

    Rejected results are retained so the funnel can report what was discarded
    and why, rather than silently shrinking.
    """
    out = []
    for result in results or []:
        classification = classify_organic_result(
            result.get("title", ""), result.get("link", "") or "",
            result.get("snippet", "") or "",
            known_business_domains=known_business_domains)
        out.append({"result": result, "classification": classification})
    return out
