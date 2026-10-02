"""Seed a SEPARATE demo database with clearly labelled sample observations.

Why this exists
---------------
The application database (``data/market_radar.db``) is git-ignored and
environment-specific, so a fresh clone starts empty. Competitors, Products and
Price Intelligence fill it by spending SerpApi credits, and the read-only
modules (Trends, Market Pulse, AI Analyst) only have something to show once
history exists -- and a *trend* needs two distinct measurements, which the
7-day response cache prevents within one week.

This script writes a small, synthetic history so those modules can be shown
end to end with no API key and no credit spent.

What it is not
--------------
Sample data, not evidence. Every business uses a reserved ``.example`` domain
and the location is literally "Sample City (demo data)", so nothing here can be
mistaken for a real market reading. It never touches the real database.

Usage (from ``backend/``)::

    python scripts/seed_demo_data.py                 # -> data/demo_market_radar.db
    python scripts/seed_demo_data.py --reset         # rebuild the demo file

Then start the API against it::

    # Windows PowerShell
    $env:DATABASE_URL="sqlite:///./data/demo_market_radar.db"; uvicorn app.main:app --port 8001
    # macOS / Linux
    DATABASE_URL=sqlite:///./data/demo_market_radar.db uvicorn app.main:app --port 8001
"""
import argparse
import os
import pathlib
import sys
from datetime import datetime, timedelta, timezone

BACKEND = pathlib.Path(__file__).resolve().parent.parent
REAL_DB = (BACKEND / "data" / "market_radar.db").resolve()
DEFAULT_DEMO_DB = BACKEND / "data" / "demo_market_radar.db"

DEMO_LOCATION = "Sample City (demo data)"
COFFEE = "Coffee Shops"
BIKES = "Bike Repair"
PRODUCT = "House Blend Coffee Beans 12oz"

# Two searches ten days apart: outside the 7-day cache window, so they are
# genuinely distinct measurements and Trends may state a direction.
FIRST = datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc)
SECOND = FIRST + timedelta(days=10)


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--database", default=str(DEFAULT_DEMO_DB),
                        help="SQLite file to create (default: data/demo_market_radar.db)")
    parser.add_argument("--reset", action="store_true",
                        help="delete and rebuild the demo file if it exists")
    return parser.parse_args()


def main():
    args = parse_args()
    target = pathlib.Path(args.database).resolve()

    if target == REAL_DB:
        sys.exit("Refusing to seed the application database. Choose another --database.")
    if target.exists():
        if not args.reset:
            sys.exit(str(target) + " already exists. Use --reset to rebuild it.")
        target.unlink()
    target.parent.mkdir(parents=True, exist_ok=True)

    # Must be set before any app module builds its engine.
    os.environ["DATABASE_URL"] = "sqlite:///" + target.as_posix()
    sys.path.insert(0, str(BACKEND))

    from app.database.base import Base
    from app.database.connection import SessionLocal, engine
    import app.models  # noqa: F401  (registers every table)
    from app.models.competitor import CompetitorObservation
    from app.models.merchant import Merchant
    from app.models.product_observation import ProductObservation
    from app.services.product_identity import canonicalise

    assert pathlib.Path(str(engine.url).replace("sqlite:///", "")).resolve() == target
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    def merchant(name, domain, address, status="verified", source="google_maps_local"):
        row = Merchant(
            name=name, normalized_name="".join(ch for ch in name.lower() if ch.isalnum()),
            website="https://" + domain + "/" if domain else None,
            normalized_domain=domain, address=address,
            status=status, entity_type="business", source=source,
            last_seen_at=SECOND, created_at=FIRST)
        db.add(row)
        db.flush()
        return row

    def seen(m, market, when, position, rating=None, reviews=None, source="local"):
        db.add(CompetitorObservation(
            merchant_id=m.id, market=market, query=market.lower(),
            location_requested=DEMO_LOCATION, location_resolved=DEMO_LOCATION,
            source_type=source, source_url=m.website, source_domain=m.normalized_domain,
            discovery_method="google_maps_local" if source == "local" else "google_organic",
            entity_type="business",
            match_method="exact_domain" if m.normalized_domain else "new",
            match_confidence="high" if source == "local" else "medium",
            status=m.status,
            reason=None if m.status == "verified" else "organic_only_evidence",
            position=position, rating=rating, reviews=reviews,
            title=m.name, snippet="Sample data for demonstration.", observed_at=when))

    def offer(m, when, product_status, price_status, price=None, reason=None,
              page_type="product"):
        db.add(ProductObservation(
            merchant_id=m.id, product_query=PRODUCT, normalized_query=canonicalise(PRODUCT),
            market=COFFEE, location_requested=DEMO_LOCATION, location_resolved=DEMO_LOCATION,
            product_name=PRODUCT if product_status == "found" else None,
            observed_size="12oz" if product_status == "found" else None,
            size_confirmed=product_status == "found",
            product_status=product_status, price_status=price_status,
            verification_reason=reason, price=price,
            currency="USD" if price is not None else None,
            source_type="merchant_website_indexed",
            source_url=("https://" + m.normalized_domain + "/products/house-blend-12oz")
            if m.normalized_domain else None,
            source_domain=m.normalized_domain, discovery_method="indexed_search",
            page_type=page_type, evidence_scope="catalog", inventory_confirmed=False,
            match_method="product_identity",
            match_reason="exact" if product_status == "found" else None,
            merchant_match_status="matched", observed_at=when))

    # ---- Coffee Shops: two distinct searches -> real trend directions -------
    bean = merchant("Sample Bean Co.", "samplebean.example", "1 Demo Street")
    roast = merchant("Example Roasters", "exampleroasters.example", "22 Sample Avenue")
    cup = merchant("Placeholder Cup Cafe", "placeholdercup.example", "5 Test Lane")
    kiosk = merchant("Demo Corner Kiosk", None, "9 Fictional Road")
    blog_found = merchant("Illustrative Coffee Guide", "illustrativecoffee.example",
                          None, status="discovered", source="google_organic")

    for when, ranks in ((FIRST, (1, 2, 3, 4)), (SECOND, (2, 1, 3, None))):
        seen(bean, COFFEE, when, ranks[0], rating=4.5 if when == FIRST else 4.6,
             reviews=120 if when == FIRST else 131)
        seen(roast, COFFEE, when, ranks[1], rating=4.3, reviews=88 if when == FIRST else 97)
        seen(cup, COFFEE, when, ranks[2], rating=4.0, reviews=40)
        if ranks[3] is not None:  # absent from the second search
            seen(kiosk, COFFEE, when, ranks[3], rating=4.8, reviews=12)
    seen(blog_found, COFFEE, SECOND, 6, source="organic")

    # Product evidence: one price rises, one stays put, one is found without a
    # verifiable price, one merchant gives no usable evidence either way.
    offer(bean, FIRST, "found", "verified", 14.99)
    offer(bean, SECOND, "found", "verified", 15.99)
    offer(roast, FIRST, "found", "verified", 13.49)
    offer(roast, SECOND, "found", "verified", 13.49)
    offer(cup, FIRST, "found", "unavailable", reason="price_not_product_specific",
          page_type="listing")
    offer(cup, SECOND, "found", "unavailable", reason="price_not_product_specific",
          page_type="listing")
    offer(blog_found, SECOND, "unknown", "unknown", reason="insufficient_evidence")

    # ---- Bike Repair: a single search -> insufficient history ---------------
    spoke = merchant("Sample Spoke Repairs", "samplespoke.example", "3 Demo Street")
    gear = merchant("Example Gear Works", "examplegear.example", "8 Sample Avenue")
    seen(spoke, BIKES, SECOND, 1, rating=4.7, reviews=55)
    seen(gear, BIKES, SECOND, 2, rating=4.2, reviews=19)

    db.commit()
    db.close()
    engine.dispose()

    print("Demo database written to " + str(target))
    print("Contexts: '" + COFFEE + "' and '" + BIKES + "' @ '" + DEMO_LOCATION + "'")
    print("Start the API with DATABASE_URL=sqlite:///" + target.as_posix())


if __name__ == "__main__":
    main()
