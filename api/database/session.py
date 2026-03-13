import os
import ssl
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from dotenv import load_dotenv

load_dotenv()

def _normalise_url(url):
    """
    Cleans the DATABASE_URL for pg8000 compatibility.
    1. Fixes postgres:// -> postgresql+pg8000://
    2. Strips ?sslmode=... which pg8000 does not support as a keyword.
    """
    if not url or url.startswith("sqlite"):
        return url

    # Handle the prefix
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+pg8000://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+pg8000://", 1)
    elif "postgresql+pg8000" not in url:
        url = url.replace("postgresql://", "postgresql+pg8000://", 1)

    # Parse the URL and strip 'sslmode' query parameter
    u = urlparse(url)
    query = parse_qs(u.query)
    
    # pg8000 fails if 'sslmode' is passed in the connection string
    if 'sslmode' in query:
        query.pop('sslmode')
    
    # Rebuild the URL without the problematic sslmode
    u = u._replace(query=urlencode(query, doseq=True))
    return urlunparse(u)

# Get and clean the URL
RAW_URL = os.getenv("DATABASE_URL", "sqlite:////tmp/clerkase.db")
DATABASE_URL = _normalise_url(RAW_URL)

# Configure the Engine
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False}
    )
else:
    # pg8000 uses ssl_context instead of sslmode
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
    try:
        from . import models
        Base.metadata.create_all(bind=engine)
        print("✓ Database initialized successfully")
    except Exception as e:
        print(f"× Database initialization failed: {e}")