"""
Database session management for ClerKase.
Supports both SQLite (local dev) and PostgreSQL (production).
Set DATABASE_URL in your .env / Vercel environment variables to switch.

PostgreSQL driver: pg8000 (pure Python — no OS-level libs needed).
The URL is rewritten automatically:
  postgresql://...   ->  postgresql+pg8000://...
  postgres://...     ->  postgresql+pg8000://...   (Vercel/Heroku short form)
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

load_dotenv()

# Default to /tmp so SQLite works on read-only filesystems (Vercel, etc.)
_raw_url = os.getenv("DATABASE_URL", "sqlite:////tmp/clerkase.db")
DB_ECHO         = os.getenv("DB_ECHO", "false").lower() == "true"
DB_POOL_SIZE    = int(os.getenv("DB_POOL_SIZE", "5"))
DB_MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "10"))


def _normalise_url(url: str) -> str:
    """
    Rewrite DATABASE_URL so SQLAlchemy uses pg8000 (pure Python) instead of
    psycopg2 for PostgreSQL connections.  Handles all common forms:
      postgresql://...          -> postgresql+pg8000://...
      postgres://...            -> postgresql+pg8000://...  (Heroku/Vercel)
      postgresql+psycopg2://... -> postgresql+pg8000://...
      sqlite:///...             -> unchanged
    """
    if url.startswith("postgres://"):
        url = "postgresql" + url[len("postgres"):]
    if url.startswith("postgresql://"):
        url = "postgresql+pg8000" + url[len("postgresql"):]
    elif url.startswith("postgresql+psycopg2://"):
        url = "postgresql+pg8000" + url[len("postgresql+psycopg2"):]
    return url


DATABASE_URL = _normalise_url(_raw_url)

if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL,
        echo=DB_ECHO,
        connect_args={"check_same_thread": False},
    )
else:
    engine = create_engine(
        DATABASE_URL,
        echo=DB_ECHO,
        pool_size=DB_POOL_SIZE,
        max_overflow=DB_MAX_OVERFLOW,
        pool_pre_ping=True,
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
    from .models import Base as ModelBase
    ModelBase.metadata.create_all(bind=engine)
    print("✓ Database tables initialised")
