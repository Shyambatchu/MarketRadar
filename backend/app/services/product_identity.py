"""Generic, industry-agnostic product identity normalisation and matching.

Discovery may be broad; verification must be strict.

Nothing in this module may reference a specific merchant, brand, product,
industry or location. Every rule here is a cross-industry rule.
"""
import re
from typing import Dict, List, Optional, Set
from urllib.parse import urlparse

NUMBER_WORDS = {
    "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4",
    "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
    "ten": "10", "eleven": "11", "twelve": "12", "thirteen": "13",
    "fourteen": "14", "fifteen": "15", "sixteen": "16", "seventeen": "17",
    "eighteen": "18", "nineteen": "19", "twenty": "20",
}

UNIT_ALIASES = {
    "litre": "l", "litres": "l", "liter": "l", "liters": "l",
    "milliliter": "ml", "millilitre": "ml", "milliliters": "ml", "millilitres": "ml",
    "ounce": "oz", "ounces": "oz", "gram": "g", "grams": "g",
    "kilogram": "kg", "kilograms": "kg", "pound": "lb", "pounds": "lb", "lbs": "lb",
    "gigabyte": "gb", "gigabytes": "gb", "terabyte": "tb", "terabytes": "tb",
    "pk": "pack", "packs": "pack", "count": "ct", "counts": "ct",
    "inches": "in", "inch": "in",
}

# Units that measure the same quantity, as multiples of one base unit, so
# "75cl", "750ml" and "0.75l" compare equal. Units absent here (oz, pack,
# gb ...) compare by their written form only.
_UNIT_SCALE = {
    "ml": ("volume", 1.0), "cl": ("volume", 10.0), "l": ("volume", 1000.0),
    "mg": ("mass", 0.001), "g": ("mass", 1.0), "kg": ("mass", 1000.0),
    "mm": ("length", 1.0), "cm": ("length", 10.0),
    "mb": ("data", 1.0), "gb": ("data", 1000.0), "tb": ("data", 1000000.0),
}

# Nouns naming an item *for* or *about* a product rather than the product:
# "iPhone 15 Case", "Cola Bottle Opener". Present on the candidate but absent
# from the request, they mean a different item. Cross-industry by design.
ACCESSORY_TOKENS = {
    "case", "cover", "sleeve", "skin", "protector", "charger", "cable",
    "adapter", "adaptor", "mount", "holder", "stand", "strap",
    "opener", "keychain", "magnet", "sticker", "decal", "poster",
    "shirt", "tshirt", "hat", "mug", "tumbler", "coaster",
    "toy", "ornament", "costume", "voucher", "manual",
    "accessory", "accessories",
}

SIZE_UNITS = "ml|l|cl|oz|g|kg|lb|gb|tb|mb|pack|ct|in|cm|mm|mg|kwh|w"
_SIZE_RE = re.compile(r"\b(\d+(?:\.\d+)?)(" + SIZE_UNITS + r")\b")

# Tokens that carry no product identity on their own. Dropping these is what
# lets "Proper No. Twelve" and "Proper Twelve" resolve to the same identity
# without weakening verification.
OPTIONAL_TOKENS = {"the", "a", "an", "of", "and", "no", "for", "with", "by", "brand", "new"}

# Cross-industry modifiers that DO change identity when present on one side
# only: iPhone Pro != iPhone Pro Max, Galaxy S25 != S25 Ultra,
# Apple Watch GPS != Apple Watch Cellular, Cola != Cola Zero.
QUALIFIER_TOKENS = {
    "max", "ultra", "pro", "plus", "mini", "micro", "lite", "light", "xl", "xs", "se",
    "cellular", "gps", "wifi", "5g", "4g", "lte",
    "reserve", "special", "limited", "edition", "anniversary", "vintage", "cask",
    "refurbished", "renewed", "used", "open", "box",
    "zero", "diet", "decaf", "unsweetened", "sugarfree",
    "kit", "bundle", "combo", "refill", "starter", "replacement",
}

_NUM_RE = re.compile(r"\d+(?:\.\d+)?$")


def canonicalise(text: str) -> str:
    """Normalise harmless differences without destroying meaningful attributes."""
    t = (text or "").lower()
    t = t.replace("&", " and ")
    t = re.sub(r"\bno\.\s*", "no ", t)
    # "15 Year Old" / "15 Yr" / "15yo" -> "15 yr"
    t = re.sub(r"\b(\d+)\s*(?:years?|yrs?|yo)\b(?:\s*old\b)?", r"\1 yr", t)
    # keep decimal points, drop all other punctuation
    t = re.sub(r"[^a-z0-9.\s]", " ", t)
    t = re.sub(r"\.(?!\d)", " ", t)
    t = re.sub(r"(?<!\d)\.", " ", t)

    words = [NUMBER_WORDS.get(w, w) for w in t.split()]
    words = [UNIT_ALIASES.get(w, w) for w in words]
    t = " ".join(words)

    # "750 ml" -> "750ml", "4 pack" -> "4pack"
    t = re.sub(r"\b(\d+(?:\.\d+)?)\s+(" + SIZE_UNITS + r")\b", r"\1\2", t)
    return re.sub(r"\s+", " ", t).strip()


def extract_sizes(text: str) -> List[str]:
    """Ordered, de-duplicated size/package tokens (deterministic)."""
    out: List[str] = []
    for m in _SIZE_RE.finditer(canonicalise(text)):
        if m.group(0) not in out:
            out.append(m.group(0))
    return out


def identity_text(title: str, url: str = "") -> str:
    """Text that may establish product identity.

    Title and URL *path* only. A result snippet describes a page, not a
    product, so it can corroborate attributes but never establish identity.
    Query strings are filters, not identity.
    """
    parts = [title or ""]
    if url:
        # A path segment that is entirely digits is a record id, not product
        # identity -- keeping it would read as a model number.
        segments = [seg for seg in (urlparse(url).path or "").split("/")
                    if seg and not seg.isdigit()]
        parts.append(re.sub(r"[-_.]+", " ", " ".join(segments)))
    return " ".join(parts)


def _size_key(size: str):
    """Comparable form of a size token: ("volume", 750.0) for "75cl"."""
    m = _SIZE_RE.fullmatch(size)
    if not m:
        return size
    unit = m.group(2)
    if unit in _UNIT_SCALE:
        dimension, scale = _UNIT_SCALE[unit]
        return (dimension, round(float(m.group(1)) * scale, 6))
    return (unit, float(m.group(1)))


def _model_numbers(tokens: Set[str], sizes: List[str]) -> Set[str]:
    return {t for t in tokens if _NUM_RE.fullmatch(t)} - set(sizes)


def match_product(query: str, candidate_title: str, snippet: str = "", url: str = "") -> Dict:
    """Strict verification of a candidate against a requested product.

    Returns {matched, reason, observed_size, detail, size_confirmed}.

    ``matched`` is product identity only. ``size_confirmed`` is a separate
    gate: a requested size that is never observed leaves product evidence
    intact but must block price verification.
    """
    result = {"matched": False, "reason": "insufficient_evidence",
              "observed_size": None, "detail": None, "size_confirmed": False}
    if not query or not (candidate_title or url):
        return result

    ident_raw = identity_text(candidate_title, url)
    q_tokens = set(canonicalise(query).split())
    i_tokens = set(canonicalise(ident_raw).split())

    q_sizes = extract_sizes(query)
    i_sizes = extract_sizes(ident_raw)
    s_sizes = extract_sizes(snippet)

    required = q_tokens - OPTIONAL_TOKENS - set(q_sizes)
    missing = required - i_tokens
    if missing:
        result["reason"] = "missing_identity_tokens"
        result["detail"] = ",".join(sorted(missing))
        return result

    accessories = (i_tokens & ACCESSORY_TOKENS) - q_tokens
    if accessories:
        # An item for the product is not the product. Not a contradiction of
        # the merchant stocking it, so it never sets not_found.
        result["reason"] = "accessory_or_related_item"
        result["detail"] = ",".join(sorted(accessories))
        return result

    extra_qualifiers = (i_tokens & QUALIFIER_TOKENS) - q_tokens
    if extra_qualifiers:
        result["reason"] = "different_variant"
        result["detail"] = ",".join(sorted(extra_qualifiers))
        return result

    # Numbers only gate identity when the request itself uses numbers as
    # identity (age, model number). Otherwise a vintage/SKU must not block.
    q_nums = _model_numbers(q_tokens, q_sizes)
    if q_nums:
        extra_nums = _model_numbers(i_tokens, i_sizes) - q_nums
        if extra_nums:
            result["reason"] = "different_model"
            result["detail"] = ",".join(sorted(extra_nums))
            return result

    q_keys = {_size_key(s) for s in q_sizes}
    if q_sizes:
        # Only the title/URL can contradict a size. A snippet often lists the
        # other sizes a page also sells ("also in 1.5l"), so it may confirm
        # the requested size but never rule it out.
        conflicting = [s for s in i_sizes if _size_key(s) not in q_keys]
        if conflicting:
            result["reason"] = "different_size"
            result["detail"] = ",".join(sorted(set(conflicting)))
            return result

    observed = i_sizes or s_sizes
    # A requested size must actually be observed before its price may be
    # verified. Identity can still hold (spec 23: product evidence may exist
    # even when the requested size cannot be confirmed).
    size_confirmed = (not q_sizes) or bool(
        q_keys & {_size_key(s) for s in i_sizes + s_sizes})
    result.update({"matched": True, "reason": "exact",
                   "observed_size": observed[0] if observed else None,
                   "size_confirmed": size_confirmed})
    return result
