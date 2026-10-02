from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from app.database.base import Base

class Business(Base):
    __tablename__ = "businesses"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    industry = Column(String)
    market = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
