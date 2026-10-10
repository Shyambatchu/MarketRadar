from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.sql import func

from app.database.base import Base


class AuditEvent(Base):
    """An append-only record of a user decision that changed stored data.

    Evidence rows are never edited, so the only mutations are human review
    actions; each one is recorded here with what changed, so a decision can be
    traced and, if needed, reversed by hand.
    """

    __tablename__ = "audit_events"

    id = Column(Integer, primary_key=True, index=True)
    entity_type = Column(String, index=True)   # merchant | opportunity | report
    entity_id = Column(Integer, index=True)
    action = Column(String)                    # e.g. review_updated
    detail = Column(Text)                      # JSON: {"field": [old, new]}
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
