from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database.base import Base

class ApiUsage(Base):
    __tablename__ = "api_usage"
    id = Column(Integer, primary_key=True, index=True)
    provider = Column(String, default="serpapi")
    endpoint = Column(String)
    query = Column(String)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    success = Column(Boolean, default=True)
    status_code = Column(Integer, nullable=True)
    response_time = Column(Float, nullable=True)
    credits_used = Column(Integer, default=1)

class SearchCache(Base):
    __tablename__ = "search_cache"
    cache_key = Column(String, primary_key=True, index=True)
    response_data = Column(Text) # JSON string
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True))

class SerpSearch(Base):
    __tablename__ = "serp_searches"
    id = Column(Integer, primary_key=True, index=True)
    query = Column(String, index=True)
    location = Column(String, nullable=True)
    engine = Column(String, default="google")
    searched_at = Column(DateTime(timezone=True), server_default=func.now())
    status = Column(String)
    response_time = Column(Float, nullable=True)
    cache_hit = Column(Boolean, default=False)
    credits_used = Column(Integer, default=0)
    
    results = relationship("SerpSearchResult", back_populates="search", cascade="all, delete")
    local_results = relationship("SerpLocalResult", back_populates="search", cascade="all, delete")

class SerpSearchResult(Base):
    __tablename__ = "serp_search_results"
    id = Column(Integer, primary_key=True, index=True)
    search_id = Column(Integer, ForeignKey("serp_searches.id"))
    position = Column(Integer)
    title = Column(String)
    link = Column(String)
    displayed_link = Column(String, nullable=True)
    snippet = Column(Text, nullable=True)
    domain = Column(String, nullable=True)
    result_type = Column(String, default="organic")
    
    search = relationship("SerpSearch", back_populates="results")

class SerpLocalResult(Base):
    __tablename__ = "serp_local_results"
    id = Column(Integer, primary_key=True, index=True)
    search_id = Column(Integer, ForeignKey("serp_searches.id"))
    position = Column(Integer)
    title = Column(String)
    type = Column(String, nullable=True)
    rating = Column(Float, nullable=True)
    reviews = Column(Integer, nullable=True)
    address = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    website = Column(String, nullable=True)
    place_id = Column(String, nullable=True)
    # The provider reports coordinates for a place; discarding them threw away
    # location data that later modules need and that costs nothing to keep.
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)

    search = relationship("SerpSearch", back_populates="local_results")
