"""Research reports: a frozen evidence snapshot, rendered for print or PDF.

A report is assembled from the same services the pages use -- Market Pulse,
the deterministic analyst, price alerts, opportunities and collected news --
for one market and location, then stored as JSON. Rendering reads only that
stored snapshot, so a report never changes after it is generated and every
figure in it is one the interface showed.

The HTML is print-ready: the browser's "Save as PDF" produces the PDF. That
keeps PDF output free of a rendering dependency; charts are inline SVG drawn
from the snapshot's own numbers, never placeholders.
"""
import html
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.news_article import NewsArticle
from app.models.report import Report
from app.services.ai_provider import get_ai_provider
from app.services.analyst_service import AnalystService
from app.services.news_service import normalize_query
from app.services.opportunity_service import DISCLAIMER as OPPORTUNITY_DISCLAIMER
from app.services.opportunity_service import OpportunityService, to_dict
from app.services.price_change_service import PriceChangeService
from app.services.pulse_service import MarketPulseService

METHODOLOGY = [
    "Observations come from SerpApi (Google Search organic and local results, Google "
    "Maps, Google Shopping, Google News, Google Trends) and are stored append-only with "
    "the time they were collected.",
    "Competitors are businesses identified from search results; a result is not proof "
    "of competition, and identity strength (verified / discovered / uncertain) is shown "
    "separately from the user's own review.",
    "Prices are verified only when found on a single-product page or a matched shopping "
    "listing, with a confirmed size and a known currency. Unverified prices are never "
    "used in statistics, alerts or opportunities.",
    "A trend or price change needs two distinct measurements; a repeated cached reading "
    "is one measurement.",
    "Opportunity scores are a weighted combination of impact, confidence, freshness and "
    "relevance, each normalised to 0-1.",
    "Any narrative text from an AI model is validated against the computed facts and "
    "withheld if it introduces a figure or an unsupported conclusion.",
]

LIMITATIONS = [
    "Search results reflect what was indexed and returned at collection time; absence "
    "from a search is not proof that a business closed or an offer ended.",
    "Catalogue evidence shows a merchant lists a product, not that a store holds stock.",
    "Google Trends interest is relative (0-100 within one request), not search volume, "
    "market share or sales.",
    "News headlines are the publishers' claims, collected as sources, not verified facts.",
    OPPORTUNITY_DISCLAIMER,
]


def build_snapshot(db: Session, market: Optional[str], location: Optional[str]) -> Dict[str, Any]:
    pulse = MarketPulseService(db).snapshot(market=market, location=location)
    analysis = AnalystService(db=db, provider=get_ai_provider()).analyse(
        market=market, location=location, include_summary=True)
    alerts = PriceChangeService(db).detect(market=market, location=location)
    opportunities = [to_dict(o) for o in
                     OpportunityService(db).list(market=market, location=location, limit=20)]
    news = []
    if market:
        for a in db.query(NewsArticle).filter(
                NewsArticle.normalized_query == normalize_query(market)).order_by(
                NewsArticle.published_at.desc().nullslast()).limit(10).all():
            news.append({"title": a.title, "link": a.link, "source_name": a.source_name,
                         "published_at": a.published_at.isoformat() if a.published_at else None})

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "parameters": {"market": market, "location": location},
        "context": pulse.context.model_dump(mode="json"),
        "has_data": pulse.has_data,
        "executive_summary": {
            "facts": [o.statement for o in analysis.market_overview + analysis.price_analysis
                      + analysis.competitor_observations][:8],
            "ai_summary": analysis.summary,
            "analysis_mode": analysis.analysis_mode,
        },
        "competitors": [c.model_dump(mode="json") for c in pulse.competitors],
        "prices": [p.model_dump(mode="json") for p in pulse.prices],
        "price_statistics": pulse.price_statistics.model_dump(mode="json"),
        "price_alerts": [a.model_dump(mode="json") for a in alerts.alerts],
        "opportunities": opportunities,
        "trends": [{"subject": t.subject, "metric": t.metric, "status": t.status,
                    "direction": t.direction, "first_value": t.first_value,
                    "last_value": t.last_value, "change_percent": t.change_percent,
                    "distinct_points": t.distinct_points}
                   for t in pulse.trends],
        "data_quality": pulse.data_quality.model_dump(mode="json"),
        "limitations_observed": [o.statement for o in analysis.data_quality],
        "news": news,
        "methodology": METHODOLOGY,
        "limitations": LIMITATIONS,
    }


def _json_default(value: Any) -> str:
    """Datetimes (e.g. on opportunities) are stored as ISO 8601 text."""
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError("Not JSON serialisable: " + type(value).__name__)


def create_report(db: Session, market: Optional[str], location: Optional[str],
                  title: Optional[str] = None) -> Report:
    market = (market or "").strip() or None
    location = (location or "").strip() or None
    snapshot = build_snapshot(db, market, location)
    report = Report(title=(title or "").strip() or ("Market report: " + (market or "all markets")
                                                    + (" / " + location if location else "")),
                    market=market, location=location,
                    snapshot=json.dumps(snapshot, default=_json_default))
    db.add(report)
    db.commit()
    return report


def summary(report: Report) -> Dict[str, Any]:
    snap = json.loads(report.snapshot or "{}")
    return {"id": report.id, "title": report.title, "market": report.market,
            "location": report.location, "created_at": report.created_at,
            "has_data": snap.get("has_data", False),
            "competitors": len(snap.get("competitors") or []),
            "verified_prices": len(snap.get("prices") or []),
            "price_alerts": len(snap.get("price_alerts") or []),
            "opportunities": len(snap.get("opportunities") or [])}


# ---------------------------------------------------------------- rendering
def _e(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def _link(url: Optional[str], text: Optional[str] = None) -> str:
    if not url or not str(url).startswith(("http://", "https://")):
        return _e(text or url or "")
    return '<a href="' + _e(url) + '">' + _e(text or url) + "</a>"


def _table(headers: List[str], rows: List[List[str]], empty: str) -> str:
    if not rows:
        return '<p class="empty">' + _e(empty) + "</p>"
    head = "".join("<th>" + _e(h) + "</th>" for h in headers)
    body = "".join("<tr>" + "".join("<td>" + c + "</td>" for c in r) + "</tr>" for r in rows)
    return "<table><thead><tr>" + head + "</tr></thead><tbody>" + body + "</tbody></table>"


def _price_chart(prices: List[Dict[str, Any]]) -> str:
    """Horizontal bars of the latest verified price per merchant, one currency."""
    latest: Dict[str, Dict[str, Any]] = {}
    for p in sorted(prices, key=lambda p: p.get("observed_at") or ""):
        latest[(p.get("merchant") or "?") + "|" + (p.get("product_query") or "")] = p
    rows = list(latest.values())
    currencies = {p.get("currency") for p in rows}
    if len(rows) < 2 or len(currencies) != 1:
        return ""
    rows.sort(key=lambda p: p["price"])
    top = max(p["price"] for p in rows) or 1
    bar_h, gap, label_w, width = 22, 8, 220, 640
    height = len(rows) * (bar_h + gap) + 10
    parts = ['<svg class="chart" viewBox="0 0 ' + str(width) + " " + str(height)
             + '" role="img" aria-label="Latest verified price by merchant">']
    for i, p in enumerate(rows):
        y = 5 + i * (bar_h + gap)
        w = max((width - label_w - 90) * p["price"] / top, 2)
        parts.append('<text x="0" y="' + str(y + 15) + '" class="lbl">'
                     + _e((p.get("merchant") or "?")[:30]) + "</text>")
        parts.append('<rect x="' + str(label_w) + '" y="' + str(y) + '" width="'
                     + str(round(w, 1)) + '" height="' + str(bar_h) + '" rx="3" class="bar"/>')
        parts.append('<text x="' + str(label_w + w + 6) + '" y="' + str(y + 15)
                     + '" class="val">' + _e("%.2f" % p["price"]) + " "
                     + _e(p.get("currency") or "") + "</text>")
    parts.append("</svg>")
    return "".join(parts)


def render_html(report: Report) -> str:
    s = json.loads(report.snapshot or "{}")
    ctx = s.get("context") or {}
    stats = s.get("price_statistics") or {}

    summary_items = "".join("<li>" + _e(f) + "</li>" for f in
                            (s.get("executive_summary") or {}).get("facts") or [])
    ai = (s.get("executive_summary") or {}).get("ai_summary")

    competitors = _table(
        ["Business", "Identity", "Review", "Sources", "First seen", "Last seen", "In latest search"],
        [[_link(c.get("website"), c.get("name")), _e(c.get("status")),
          _e(c.get("review_status") or "unreviewed"),
          _e(", ".join(c.get("discovery_sources") or [])), _e((c.get("first_seen_at") or "")[:10]),
          _e((c.get("last_seen_at") or "")[:10]), "yes" if c.get("present_in_latest") else "no"]
         for c in s.get("competitors") or []],
        "No competitors were observed for this selection.")

    prices = _table(
        ["Merchant", "Product", "Size", "Price", "Observed", "Source"],
        [[_e(p.get("merchant")), _e(p.get("product_name") or p.get("product_query")),
          _e(p.get("observed_size")), _e("%.2f %s" % (p["price"], p.get("currency") or "")),
          _e((p.get("observed_at") or "")[:10]), _link(p.get("source_url"), p.get("source_domain"))]
         for p in s.get("prices") or []],
        "No verified prices were observed for this selection.")

    stats_text = (_e("Lowest %.2f, average %.2f, highest %.2f %s across %d distinct measurements."
                     % (stats["lowest"], stats["average"], stats["highest"],
                        stats.get("currency") or "", stats["distinct_measurements"]))
                  if stats.get("sufficient") else _e(stats.get("detail") or
                                                     "Not enough distinct measurements for statistics."))

    alerts = _table(
        ["Type", "Product", "Merchant", "Change", "Confidence", "Evidence"],
        [[_e(a["type"].replace("_", " ")), _e(a.get("product")), _e(a.get("merchant")),
          _e(("%+.2f%%" % a["change_percent"]) if a.get("change_percent") is not None else ""),
          _e(a.get("confidence")),
          "<br>".join(_link(u) for u in (a.get("source_urls") or [])[:3])]
         for a in s.get("price_alerts") or []],
        "No price change met the detection thresholds.")

    opportunities = _table(
        ["Score", "Opportunity", "Category", "Confidence", "Next action"],
        [[_e(o.get("score")), _e(o.get("title")), _e((o.get("category") or "").replace("_", " ")),
          _e(o.get("confidence")), _e(o.get("suggested_action"))]
         for o in s.get("opportunities") or []],
        "No opportunities have been generated for this selection. Refresh opportunities first.")

    trends = _table(
        ["Subject", "Metric", "Status", "Direction", "First", "Last", "Distinct points"],
        [[_e(t.get("subject")), _e(t.get("metric")), _e(t.get("status")),
          _e(t.get("direction")), _e(t.get("first_value")), _e(t.get("last_value")),
          _e(t.get("distinct_points"))] for t in s.get("trends") or []],
        "No trend series exist for this selection.")

    news = _table(
        ["Published", "Headline (publisher's claim)", "Source"],
        [[_e((n.get("published_at") or "")[:10]), _link(n.get("link"), n.get("title")),
          _e(n.get("source_name"))] for n in s.get("news") or []],
        "No news has been collected for this market.")

    def bullets(items):
        return "<ul>" + "".join("<li>" + _e(i) + "</li>" for i in items) + "</ul>"

    return """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>""" + _e(report.title) + """</title>
<style>
:root{--ink:#1b2430;--muted:#5b6675;--line:#d9dee5;--accent:#2457c5;--bg:#fff}
*{box-sizing:border-box}body{font:14px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif;color:var(--ink);background:var(--bg);margin:0;padding:32px;max-width:1000px;margin:auto}
h1{font-size:24px;margin:0 0 4px}h2{font-size:17px;margin:28px 0 8px;padding-bottom:4px;border-bottom:1px solid var(--line)}
.meta{color:var(--muted);font-size:13px}.empty{color:var(--muted);font-style:italic}
table{width:100%;border-collapse:collapse;font-size:12.5px;margin:6px 0}th,td{text-align:left;padding:5px 6px;border-bottom:1px solid var(--line);vertical-align:top}
th{background:#f4f6f9;font-weight:600}a{color:var(--accent);word-break:break-word}
.note{background:#f4f6f9;border-left:3px solid var(--accent);padding:8px 12px;font-size:13px}
.chart{width:100%;max-width:640px;margin:8px 0}.chart .bar{fill:var(--accent)}.chart .lbl,.chart .val{font-size:12px;fill:var(--ink)}
.toolbar{margin:12px 0 0}.toolbar button{font:inherit;padding:6px 14px;border:1px solid var(--line);background:#fff;border-radius:6px;cursor:pointer}
@media print{.toolbar{display:none}body{padding:0}h2{break-after:avoid}tr{break-inside:avoid}}
</style></head><body>
<h1>""" + _e(report.title) + """</h1>
<div class="meta">Market: <b>""" + _e(ctx.get("market") or "all markets") + """</b> &middot;
Location: <b>""" + _e(ctx.get("location") or "all locations") + """</b><br>
Report generated """ + _e(s.get("generated_at", "")[:19].replace("T", " ")) + """ UTC &middot;
Evidence collected """ + _e((ctx.get("first_observed_at") or "")[:10]) + " to " + _e((ctx.get("last_observed_at") or "")[:10]) + """ &middot;
""" + _e(ctx.get("distinct_searches", 0)) + """ distinct searches, """ + _e(ctx.get("merchants", 0)) + """ businesses</div>
<div class="toolbar"><button onclick="window.print()">Print / Save as PDF</button></div>

<h2>Executive summary</h2>
""" + ("<ul>" + summary_items + "</ul>" if summary_items else '<p class="empty">No observations for this selection.</p>') + (
        '<p class="note"><b>AI-written summary (validated against the facts above):</b> ' + _e(ai) + "</p>"
        if ai else "") + """
<h2>Competitors</h2>""" + competitors + """
<h2>Verified prices</h2>""" + _price_chart(s.get("prices") or []) + prices + "<p>" + stats_text + """</p>
<h2>Price changes</h2>""" + alerts + """
<h2>Opportunities</h2><p class="meta">""" + _e(OPPORTUNITY_DISCLAIMER) + "</p>" + opportunities + """
<h2>Trends</h2>""" + trends + """
<h2>News</h2>""" + news + """
<h2>Data quality</h2>""" + (bullets(s.get("limitations_observed") or []) or "") + """
<h2>Methodology</h2>""" + bullets(s.get("methodology") or []) + """
<h2>Limitations</h2>""" + bullets(s.get("limitations") or []) + """
<p class="meta">Generated by MarketRadar from stored observations. Every figure above comes from
the evidence snapshot captured when the report was generated.</p>
</body></html>"""
