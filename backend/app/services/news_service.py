"""Market news from Google News (SerpApi ``google_news``).

News is collected as *pointers to sources*: title, publisher, link and the
publication time the provider reports. Nothing here reads, summarises or
vouches for an article; a headline is the publisher's claim, not a verified
fact, and the UI says so.

Articles are deduplicated per query and link, so re-running a search refreshes
``last_seen_at`` rather than storing the same article twice. One credit per
uncached search (cached 6 h).
"""
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.news_article import NewsArticle
from app.services.api_budget import ApiBudgetManager
from app.services.serpapi_organic_service import (
    SerpApiNotConfiguredError, SerpApiProviderError,
)

CACHE_TTL_HOURS = 6
MAX_QUERY_LENGTH = 200
_GL_RE = re.compile(r"^[a-z]{2}$")
_HL_RE = re.compile(r"^[a-z]{2}(-[a-z]{2})?$")


def normalize_query(q: str) -> str:
    return " ".join((q or "").lower().split())


def _parse_iso(value: Any) -> Optional[datetime]:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def flatten(results: Any) -> List[Dict[str, Any]]:
    """Top-level results plus the stories clustered under them."""
    out: List[Dict[str, Any]] = []
    for item in results if isinstance(results, list) else []:
        if not isinstance(item, dict):
            continue
        if item.get("link") and item.get("title"):
            out.append(item)
        for story in item.get("stories") or []:
            if isinstance(story, dict) and story.get("link") and story.get("title"):
                out.append(story)
    return out


def _source_name(item: Dict[str, Any]) -> Optional[str]:
    source = item.get("source")
    if isinstance(source, dict):
        return source.get("name")
    return source if isinstance(source, str) else None


class NewsService:
    def __init__(self, db: Session, api_key: Optional[str] = None):
        self.db = db
        self.api_key = api_key

    def search(self, q: str, gl: str = "us", hl: str = "en", sort: str = "relevance",
               persist: bool = True) -> Dict[str, Any]:
        q = (q or "").strip()
        if len(q) < 2:
            raise ValueError("A news query of at least 2 characters is required.")
        if len(q) > MAX_QUERY_LENGTH:
            raise ValueError("The news query must be at most " + str(MAX_QUERY_LENGTH)
                             + " characters.")
        gl, hl = (gl or "us").lower(), (hl or "en").lower()
        if not _GL_RE.match(gl) or not _HL_RE.match(hl):
            raise ValueError("gl must be a 2-letter country code and hl a language code "
                             "such as 'en' or 'en-gb'.")
        if sort not in ("relevance", "date"):
            raise ValueError("sort must be 'relevance' or 'date'.")
        if not self.api_key:
            raise SerpApiNotConfiguredError("SerpApi key not configured.")

        budget = ApiBudgetManager(self.db, self.api_key)
        params = {"engine": "google_news", "q": q, "gl": gl, "hl": hl}
        if sort == "date":
            params["so"] = "1"
        hits = budget.cache_hits
        data = budget.execute_search(
            "v1|news|" + normalize_query(q) + "|" + gl + "|" + hl + "|" + sort,
            params, "google_news", ttl_hours=CACHE_TTL_HOURS)
        if data is None:
            raise SerpApiProviderError(budget.last_error or "Google News did not respond.")
        cache_hit = budget.cache_hits > hits

        now = datetime.now(timezone.utc)
        articles = []
        norm = normalize_query(q)
        seen_links = set()
        for item in flatten(data.get("news_results")):
            link = item["link"]
            if link in seen_links:
                continue
            seen_links.add(link)
            article = {
                "title": item["title"], "link": link, "source_name": _source_name(item),
                "published_at": _parse_iso(item.get("iso_date")),
                "published_label": item.get("date"), "position": item.get("position"),
            }
            if persist:
                row = self.db.query(NewsArticle).filter(
                    NewsArticle.normalized_query == norm, NewsArticle.link == link).first()
                if row is None:
                    row = NewsArticle(query=q, normalized_query=norm, gl=gl, hl=hl,
                                      first_seen_at=now, **article)
                    self.db.add(row)
                row.last_seen_at = now
            articles.append(article)
        if persist:
            self.db.commit()

        if sort == "date":
            articles.sort(key=lambda a: a["published_at"] or datetime.min.replace(
                tzinfo=timezone.utc), reverse=True)
        return {"query": q, "gl": gl, "hl": hl, "sort": sort, "cache_hit": cache_hit,
                "collected_at": now, "total": len(articles), "articles": articles,
                "provider_status": "success" if articles else "no_results",
                "detail": "Headlines are the publishers' claims, collected as sources; "
                          "they are not verified facts."}

    def saved(self, q: Optional[str] = None, limit: int = 100) -> Dict[str, Any]:
        query = self.db.query(NewsArticle)
        if q:
            query = query.filter(NewsArticle.normalized_query == normalize_query(q))
        total = query.count()
        rows = query.order_by(NewsArticle.published_at.desc().nullslast(),
                              NewsArticle.id.desc()).limit(limit).all()
        return {"total": total, "articles": [{
            "id": r.id, "query": r.query, "title": r.title, "link": r.link,
            "source_name": r.source_name, "published_at": r.published_at,
            "published_label": r.published_label, "first_seen_at": r.first_seen_at,
            "last_seen_at": r.last_seen_at} for r in rows]}
