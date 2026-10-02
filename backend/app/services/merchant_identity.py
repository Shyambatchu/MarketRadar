"""Generic merchant identity resolution.

Spec 24 priority, applied as ranked tiers across ALL candidate merchants --
never first-merchant-wins. A tier that matches more than one nearby merchant
is ambiguous (a chain with several stores in radius) and must resolve to
"uncertain", which may never become a verified store-level price.
"""
import re
from typing import Dict, List, Optional
from urllib.parse import urlparse

_STOPWORDS = {"inc", "llc", "ltd", "co", "corp", "the", "store", "shop", "market"}

# Tier -> confidence. Ordered strongest first.
TIERS = [
    ("exact_domain", "high"),
    ("domain_alias", "high"),
    ("exact_name", "medium"),
    ("name_and_address", "medium"),
    ("fuzzy_name", "low"),
]

# Minimum normalised-name length before substring matching is allowed at all,
# so short generic names cannot swallow unrelated merchants.
_MIN_FUZZY_LEN = 8


def normalize_domain(url: str) -> str:
    if not url:
        return ""
    if not url.startswith("http"):
        url = "http://" + url
    netloc = urlparse(url).netloc.lower().split(":")[0]
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return netloc


def normalize_name(name: str) -> str:
    if not name:
        return ""
    n = re.sub(r"[^a-z0-9\s]", " ", (name or "").lower())
    words = [w for w in n.split() if w not in _STOPWORDS]
    return "".join(words)


def host_matches_domain(link: str, domain: str) -> bool:
    """True only when ``link`` is actually served by ``domain``."""
    if not link or not domain:
        return False
    host = normalize_domain(link)
    return host == domain or host.endswith("." + domain)


def _tier_candidates(tier: str, source_domain: str, source_name: str,
                     source_address: str, merchants: List[Dict],
                     aliases: Dict[str, str]) -> List[Dict]:
    src_norm = normalize_name(source_name)
    out = []
    for m in merchants:
        m_domain = m.get("domain") or ""
        m_norm = m.get("normalized_name") or ""
        if tier == "exact_domain":
            if source_domain and m_domain and source_domain == m_domain:
                out.append(m)
        elif tier == "domain_alias":
            if source_domain and m_domain and aliases.get(source_domain) == m_domain:
                out.append(m)
        elif tier == "exact_name":
            if src_norm and m_norm and src_norm == m_norm:
                out.append(m)
        elif tier == "name_and_address":
            if src_norm and m_norm and source_address and m.get("address"):
                if src_norm == m_norm and source_address.lower()[:12] in m["address"].lower():
                    out.append(m)
        elif tier == "fuzzy_name":
            if not src_norm or not m_norm:
                continue
            if min(len(src_norm), len(m_norm)) < _MIN_FUZZY_LEN:
                continue
            if m_norm in src_norm or src_norm in m_norm:
                out.append(m)
    return out


def match_merchant(source_domain: str, source_name: str,
                   merchants: List[Dict], source_address: str = "",
                   aliases: Optional[Dict[str, str]] = None) -> Dict:
    """Resolve a result to a nearby merchant using the full tier hierarchy.

    status: matched | uncertain | unmatched
    """
    aliases = aliases or {}
    for tier, confidence in TIERS:
        hits = _tier_candidates(tier, source_domain, source_name,
                                source_address, merchants, aliases)
        if not hits:
            continue
        if len(hits) > 1:
            # Same identity evidence points at several nearby stores -- e.g. a
            # chain. We cannot say which physical store this concerns.
            return {"merchant": None, "status": "uncertain", "method": tier,
                    "confidence": "low", "ambiguous_count": len(hits),
                    "candidates": hits}
        status = "uncertain" if confidence == "low" else "matched"
        return {"merchant": hits[0], "status": status, "method": tier,
                "confidence": confidence, "ambiguous_count": 1,
                "candidates": hits}
    return {"merchant": None, "status": "unmatched", "method": "unmatched",
            "confidence": "unmatched", "ambiguous_count": 0, "candidates": []}
