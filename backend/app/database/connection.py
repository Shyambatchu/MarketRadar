from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.config import settings
import os

db_url = settings.DATABASE_URL
if db_url.startswith("sqlite"):
    # Ensure data dir exists
    os.makedirs(os.path.dirname(db_url.split("///")[-1]), exist_ok=True)
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
else:
    engine = create_engine(db_url)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
