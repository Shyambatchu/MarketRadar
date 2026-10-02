"""Merchant website evidence via Google-indexed results.

Two hard rules enforced here:

1. A result may only be attributed to a merchant domain when the result is
   actually served by that domain. A ``site:`` query that finds nothing falls
   back to general web results; those are not merchant evidence.
2. A price may only be carried forward for verification when it came from a
   single-product page. Prices lifted from a filtered brand/category listing
   belong to "some product in this list", not to the requested product.
"""
import re
from typing import Dict, List, Optional
from urllib.parse import urlparse, parse_qs

from app.services.api_budget import ApiBudgetManager
from app.services.merchant_identity import host_matches_domain

# Query-string keys indicating a filtered listing/search page, not a product.
LISTING_QUERY_KEYS = {
    "brand", "brands", "category", "categories", "collection", "collections",
    "subtype", "subtypes", "type", "types", "tag", "tags", "filter", "filters",
    "q", "s", "search", "keyword", "query", "sort", "orderby", "page", "varietal",
}
# Path segments naming a single product.
PRODUCT_PATH_SEGMENTS = {"product", "products", "item", "items", "p", "dp", "sku", "gp"}
# Path segments naming a listing.
LISTING_PATH_SEGMENTS = {
    "shop", "store", "catalog", "collections", "collection", "category",
    "categories", "brands", "brand", "search", "results", "tag", "tags", "department",
}


def classify_page_type(url: str) -> str:
    """product | listing | unknown -- generic across storefront platforms."""
    if not url:
        return "unknown"
    parsed = urlparse(url)
    segments = [s.lower() for s in parsed.path.split("/") if s]

    # A product segment followed by a slug identifies one product.
    for i, seg in enumerate(segments):
        if seg in PRODUCT_PATH_SEGMENTS and i < len(segments) - 1:
            return "product"

    if any(k.lower() in LISTING_QUERY_KEYS for k in parse_qs(parsed.query)):
        return "listing"
    # No product segment anywhere, but a listing segment -> a listing page.
    if any(seg in LISTING_PATH_SEGMENTS for seg in segments):
        return "listing"
    return "unknown"


class MerchantWebsitePriceProvider:
    def __init__(self):
        pass

    def extract_price_info(self, title: str, snippet: str, search_product: str) -> dict:
        text = f"{title} ... {snippet}"

        if re.search(r'\$(\d+\.\d{2})\s*(?:-|–|to)\s*\$(\d+\.\d{2})', text):
            return {"price": None, "is_range": True, "ambiguous_price": False, "segment": text}

        if re.search(r'(?i)(?:starting at|starts at|from|as low as)\s*\$\d+\.\d{2}', text):
            return {"price": None, "is_range": False, "ambiguous_price": True, "segment": text}

        segments = re.split(r'(?:\.\.\.|\. | \| | - )', text)

        def tokenize(t):
            return set(re.sub(r'[^a-z0-9\s]', '', t.lower()).split())

        def extract_sizes(t):
            sizes = set(re.findall(
                r'\b\d+(?:\.\d+)?\s*(?:ml|l|oz|g|kg|lb|pack|pk|gb|tb|in|inch|cm|mm|mg)\b',
                t.lower()))
            return {s.replace(' ', '') for s in sizes}

        sp_tokens = tokenize(search_product)
        sp_sizes = extract_sizes(search_product)

        best_segment, best_score, best_price = None, -999, None

        for seg in segments:
            prices = re.findall(r'\$(\d+\.\d{2})', seg)
            if not prices:
                continue
            if len(prices) == 1:
                seg_price = float(prices[0])
            elif re.search(r'(?i)was|now|sale|save|regular', seg):
                seg_price = min(float(p) for p in prices)
            else:
                continue

            score = len(sp_tokens.intersection(tokenize(seg)))
            if extract_sizes(seg) - sp_sizes:
                score -= 100
            if score > best_score:
                best_score, best_segment, best_price = score, seg, seg_price

        if best_price is not None and best_score >= 0:
            return {"price": best_price, "is_range": False,
                    "ambiguous_price": False, "segment": best_segment}

        all_prices = re.findall(r'\$(\d+\.\d{2})', text)
        if len(all_prices) == 1:
            return {"price": float(all_prices[0]), "is_range": False,
                    "ambiguous_price": False, "segment": text}
        if len(all_prices) > 1:
            return {"price": None, "is_range": False, "ambiguous_price": True, "segment": text}

        return {"price": None, "is_range": False, "ambiguous_price": False, "segment": text}

    def discover_prices(self, merchant: Dict, product: str,
                        budget_manager: ApiBudgetManager,
                        cache_version: str = "v1",
                        hl: str = "en", gl: str = "us") -> Dict:
        """Returns {status, observations, rows_returned, off_domain_rejected}."""
        domain = merchant.get("domain")
        if not domain:
            return {"status": "skipped", "detail": "merchant_has_no_domain",
                    "observations": [], "rows_returned": 0, "off_domain_rejected": 0}

        # Language and country change which indexed rows come back, so they are
        # part of the cache identity alongside the domain and the product.
        cache_key = f"{cache_version}|merchant_website_indexed|{domain}|{product}|{hl}|{gl}"
        params = {"engine": "google", "q": f"site:{domain} {product}", "hl": hl, "gl": gl}

        results = budget_manager.execute_search(
            cache_key, params, "merchant_website_indexed", domain=domain)
        if results is None:
            return {"status": "error", "detail": "provider_request_failed",
                    "observations": [], "rows_returned": 0, "off_domain_rejected": 0}

        organic = results.get("organic_results", []) or []
        observations, off_domain = [], 0

        for res in organic:
            link = res.get("link", "")
            # Rule 1: a site: query with no hits falls back to the open web.
            if not host_matches_domain(link, domain):
                off_domain += 1
                continue

            title = res.get("title", "")
            snippet = res.get("snippet", "")
            info = self.extract_price_info(title, snippet, product)
            page_type = classify_page_type(link)

            observations.append({
                "title": title,
                "snippet": info["segment"],
                "raw_snippet": snippet,
                "url": link,
                "price": info["price"],
                "availability": "In Stock" if re.search(
                    r'(?i)add to cart|in stock|available', snippet) else None,
                "source_type": "merchant_website_indexed",
                "source_domain": domain,
                "page_type": page_type,
                "is_range": info["is_range"],
                "ambiguous_price": info["ambiguous_price"],
            })

        return {"status": "ok", "detail": None, "observations": observations,
                "rows_returned": len(organic), "off_domain_rejected": off_domain}
