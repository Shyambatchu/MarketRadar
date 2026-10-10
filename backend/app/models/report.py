from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.sql import func

from app.database.base import Base


class Report(Base):
    """A saved research report: its parameters and a frozen evidence snapshot.

    The snapshot is captured when the report is generated, so re-opening it
    later shows exactly what was reported then -- even after new observations
    arrive -- with the collection timestamps that were current at the time.
    """

    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String)
    market = Column(String, nullable=True, index=True)
    location = Column(String, nullable=True)
    snapshot = Column(Text)        # JSON
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
