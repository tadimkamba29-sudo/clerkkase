import os
import ssl
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from dotenv import load_dotenv

load_dotenv()

def _normalise_url(url):
    """
    Cleans the DATABASE_URL for Vercel + pg8000 compatibility.
    """
    if not url or url.startswith("sqlite"):
        return url

    # Force the driver to pg8000 (pure python, no binary issues)
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+pg8000://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+pg8000://", 1)
    elif "postgresql+pg8000" not in url:
        url = url.replace("postgresql://", "postgresql+pg8000://", 1)

    # Strip 'sslmode' which pg8000 doesn't recognize as a URL parameter
    u = urlparse(url)
    query = parse_qs(u.query)
    if 'sslmode' in query:
        query.pop('sslmode')
    
    u = u._replace(query=urlencode(query, doseq=True))
    return urlunparse(u)

# Get URL and clean it
RAW_URL = os.getenv("DATABASE_URL", "sqlite:////tmp/clerkase.db")
DATABASE_URL = _normalise_url(RAW_URL)

# Configure Engine
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False}
    )
else:
    # Use SSL context for pg8000
    engine = create_engine(
        DATABASE_URL,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
        connect_args={
            "ssl_context": ssl.create_default_context()
        }
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Called by state_manager or index.py to setup tables."""
    try:
        from . import models
        Base.metadata.create_all(bind=engine)
        return True
    except Exception as e:
        print(f"Database init failed: {e}")
        return False