"""
Database session management for ClerKase.
Supports both SQLite (local dev) and PostgreSQL (production).
Set DATABASE_URL in your .env / Vercel environment variables to switch.

PostgreSQL driver: pg8000 (pure Python — no OS-level libs needed).
The URL is rewritten automatically:
  postgresql://...   ->  postgresql+pg8000://...
  postgres://...     ->  postgresql+pg8000://...   (Vercel/Heroku short form)
"""

"""
Database session management
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///clerkase.db")
DB_ECHO = os.getenv("DB_ECHO", "false").lower() == "true"
DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "5"))
DB_MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "10"))

# Fix 1: Vercel Postgres gives "postgres://" — SQLAlchemy needs "postgresql://"
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL,
        echo=DB_ECHO,
        connect_args={"check_same_thread": False}
    )
else:
    # Fix 2: Remove sslmode from URL entirely — pass it via connect_args
    # This works for psycopg2. asyncpg uses ssl=True but we're using psycopg2-binary.
    if "sslmode" in DATABASE_URL:
        from urllib.parse import urlparse, urlencode, parse_qs, urlunparse
        parsed = urlparse(DATABASE_URL)
        # Remove sslmode from query string
        query_params = {k: v for k, v in 
                       [p.split("=") for p in parsed.query.split("&") if "=" in p]
                       if k != "sslmode"}
        clean_url = parsed._replace(query="&".join(f"{k}={v}" for k, v in query_params.items()))
        DATABASE_URL = urlunparse(clean_url)

    engine = create_engine(
        DATABASE_URL,
        echo=DB_ECHO,
        pool_size=DB_POOL_SIZE,
        max_overflow=DB_MAX_OVERFLOW,
        pool_pre_ping=True,
        connect_args={"sslmode": "require"}  # psycopg2 accepts this in connect_args
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
    from .models import Base
    Base.metadata.create_all(bind=engine)
    print("✓ Database initialized")