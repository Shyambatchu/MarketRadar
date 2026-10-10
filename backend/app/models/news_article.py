from sqlalchemy import Column, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.sql import func

from app.database.base import Base


class NewsArticle(Base):
    """A news result collected for a query, deduplicated per query and link.

    A search result is a pointer to a source, not a verified fact: the title
    is the publisher's, and nothing here asserts what the article says is true.
    """

    __tablename__ = "news_articles"
    __table_args__ = (UniqueConstraint("normalized_query", "link", name="uq_news_query_link"),)

    id = Column(Integer, primary_key=True, index=True)
    query = Column(String)
    normalized_query = Column(String, index=True)
    gl = Column(String, nullable=True)
    hl = Column(String, nullable=True)
    title = Column(Text)
    link = Column(String)
    source_name = Column(String, nullable=True, index=True)
    published_at = Column(DateTime(timezone=True), nullable=True, index=True)
    published_label = Column(String, nullable=True)   # the provider's display date
    position = Column(Integer, nullable=True)
    first_seen_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    last_seen_at = Column(DateTime(timezone=True), nullable=True)
