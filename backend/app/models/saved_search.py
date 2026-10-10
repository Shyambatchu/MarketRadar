from sqlalchemy import Column, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.sql import func

from app.database.base import Base


class SavedSearch(Base):
    """A research query the user chose to keep, to re-run later."""

    __tablename__ = "saved_searches"
    __table_args__ = (UniqueConstraint("module", "query", "location",
                                       name="uq_saved_search"),)

    id = Column(Integer, primary_key=True, index=True)
    module = Column(String, index=True)     # research | competitors | products | prices | interest | news
    label = Column(String, nullable=True)
    query = Column(String)
    market = Column(String, nullable=True)
    location = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
