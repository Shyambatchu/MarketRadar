"""Price text -> (amount, currency), without assuming one country.

Every price used to be read from ``$NN.NN`` text and labelled USD, so a market
outside the US produced no prices at all, and a Canadian or Australian "$" was
silently called US dollars. This module is the one place a price string is
interpreted.

Rules, all conservative:

* A currency is only ever taken from the text itself (a symbol or an ISO code)
  or, for the bare "$" symbol, from the market's country. Nothing else is
  guessed. When neither settles it the currency is ``None`` -- and a price
  with no currency is never treated as verified downstream.
* Both decimal conventions are read: "1,234.56" and "1.234,56". A figure whose
  separator could mean either ("1,234" / "1.234") is read as a thousands
  separator only when exactly three digits follow it.
* Several different currencies in one string make it ambiguous; no amount is
  chosen between them.
"""
import re
from typing import List, NamedTuple, Optional

# Longest first, so "US$" is not read as "$".
_SYMBOLS = {
    "US$": "USD", "U.S.$": "USD", "CA$": "CAD", "C$": "CAD", "AU$": "AUD",
    "A$": "AUD", "NZ$": "NZD", "HK$": "HKD", "S$": "SGD", "R$": "BRL",
    "€": "EUR", "£": "GBP", "₹": "INR", "Rs.": "INR", "Rs": "INR",
    "¥": "JPY", "₩": "KRW", "₱": "PHP", "₦": "NGN", "zł": "PLN", "kr": None,
    "$": None,  # resolved from the market's country
}
_CODES = ("USD", "EUR", "GBP", "INR", "CAD", "AUD", "NZD", "JPY", "CNY", "CHF",
          "SEK", "NOK", "DKK", "PLN", "BRL", "MXN", "SGD", "HKD", "ZAR", "AED",
          "KRW", "PHP", "NGN")

# Countries whose own currency is written "$". Anything else leaves "$"
# unresolved rather than defaulting to US dollars.
_DOLLAR_BY_COUNTRY = {
    "us": "USD", "ca": "CAD", "au": "AUD", "nz": "NZD", "sg": "SGD",
    "hk": "HKD", "mx": "MXN", "ar": "ARS", "cl": "CLP", "co": "COP",
}
_KRONA_BY_COUNTRY = {"se": "SEK", "no": "NOK", "dk": "DKK"}

_SYMBOL_RE = "|".join(re.escape(s) for s in sorted(_SYMBOLS, key=len, reverse=True))
_CODE_RE = "|".join(_CODES)
# An amount with an optional thousands grouping and an optional 1-2 digit
# decimal part, in either convention.
_AMOUNT_RE = r"\d{1,3}(?:[,. ]\d{3})+(?:[.,]\d{1,2})?|\d+(?:[.,]\d{1,2})?"

PRICE_RE = re.compile(
    r"(?:(?P<pre>" + _SYMBOL_RE + r"|\b(?:" + _CODE_RE + r"))\s?(?P<a1>" + _AMOUNT_RE + r"))"
    r"|(?:(?P<a2>" + _AMOUNT_RE + r")\s?(?P<post>€|£|₹|zł|kr\b|\b(?:" + _CODE_RE + r")\b)"
    # A symbol directly followed by a number belongs to that number:
    # "Widget 2000 €24,90" is €24.90, not €2000.
    r"(?!\s?\d))"
)


class PriceMatch(NamedTuple):
    amount: float
    currency: Optional[str]
    raw: str


def dollar_currency(country: Optional[str]) -> Optional[str]:
    return _DOLLAR_BY_COUNTRY.get((country or "").lower())


def currency_for_country(country: Optional[str]) -> Optional[str]:
    """The currency a bare local symbol means in ``country``, if known."""
    country = (country or "").lower()
    return _DOLLAR_BY_COUNTRY.get(country) or _KRONA_BY_COUNTRY.get(country)


def parse_amount(text: str) -> Optional[float]:
    """"1,234.56" / "1.234,56" / "1 234,56" / "39.99" / "39" -> float."""
    if text is None:
        return None
    s = str(text).strip().replace(" ", " ")
    if not s:
        return None
    s = s.replace(" ", "")
    if "," in s and "." in s:
        # Whichever separator comes last is the decimal point.
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s or "." in s:
        sep = "," if "," in s else "."
        head, _, tail = s.rpartition(sep)
        if s.count(sep) > 1 or len(tail) == 3:
            s = s.replace(sep, "")           # thousands grouping
        else:
            s = head.replace(sep, "") + "." + tail
    try:
        value = float(s)
    except ValueError:
        return None
    return value if value >= 0 else None


def _resolve(symbol: Optional[str], country: Optional[str]) -> Optional[str]:
    if not symbol:
        return None
    symbol = symbol.strip()
    if symbol.upper() in _CODES:
        return symbol.upper()
    if symbol == "$":
        return dollar_currency(country)
    if symbol == "kr":
        return _KRONA_BY_COUNTRY.get((country or "").lower())
    return _SYMBOLS.get(symbol)


def find_prices(text: str, country: Optional[str] = None) -> List[PriceMatch]:
    """Every symbol- or code-marked amount in ``text``. Bare numbers are not
    prices: "750" in "750ml" must never become one."""
    out: List[PriceMatch] = []
    for m in PRICE_RE.finditer(text or ""):
        symbol = m.group("pre") or m.group("post")
        amount = parse_amount(m.group("a1") or m.group("a2"))
        if amount is None:
            continue
        out.append(PriceMatch(amount, _resolve(symbol, country), m.group(0)))
    return out


def parse_price(text: str, country: Optional[str] = None) -> Optional[PriceMatch]:
    """The single price in ``text``, or None when there is none or several
    that disagree. A bare number with no marker is parsed with currency None."""
    matches = find_prices(text, country)
    if not matches:
        # Only a value that is nothing but a number (a structured provider
        # field such as "39.99") -- never digits picked out of prose.
        if re.fullmatch(r"\s*(?:" + _AMOUNT_RE + r")\s*", text or ""):
            amount = parse_amount(text)
            return PriceMatch(amount, None, text) if amount is not None else None
        return None
    distinct = {(m.amount, m.currency) for m in matches}
    return matches[0] if len(distinct) == 1 else None
