import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

load_dotenv()

def _normalise_url(url):
    """
    Cleans the DATABASE_URL for Vercel + Psycopg 3 compatibility.
    1. Fixes postgres:// -> postgresql+psycopg://
    2. Standardizes the prefix for SQLAlchemy 2.0
    """
    if not url or url.startswith("sqlite"):
        return url

    # Force Psycopg 3 (the modern, robust driver)
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    elif "postgresql+psycopg" not in url:
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
        
    return url

# Get URL from environment
RAW_URL = os.getenv("DATABASE_URL", "sqlite:////tmp/clerkase.db")
DATABASE_URL = _normalise_url(RAW_URL)

# Configure the Engine
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False}
    )
else:
    # Psycopg 3 handles sslmode=require in the URL automatically.
    # We use pool_pre_ping to handle serverless connection drops.
    engine = create_engine(
        DATABASE_URL,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True
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
    """Initializes the database tables."""
    try:
        from . import models
        Base.metadata.create_all(bind=engine)
        print("✓ Database initialized successfully")
        return True
    except Exception as e:
        print(f"× Database initialization failed: {e}")
        return False