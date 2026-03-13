"""
Database session management for ClerKase.
Supports both SQLite (local dev) and PostgreSQL (production).
Set DATABASE_URL in your .env to switch between them.
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

# SQLite needs check_same_thread=False for Flask's threaded requests.
# PostgreSQL gets connection pooling instead.
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL,
        echo=DB_ECHO,
        connect_args={"check_same_thread": False}
    )
else:
    engine = create_engine(
        DATABASE_URL,
        echo=DB_ECHO,
        pool_size=DB_POOL_SIZE,
        max_overflow=DB_MAX_OVERFLOW,
        pool_pre_ping=True   # Drops stale connections before reuse
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """
    Context-manager style session for Flask routes.

    Usage:
        db = next(get_db())
        try:
            ...
        finally:
            db.close()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Create all tables. Call once at application startup.
    Safe to call repeatedly — won't drop existing data.
    """
    from .models import Base as ModelBase  # local import avoids circular deps
    ModelBase.metadata.create_all(bind=engine)
    print("✓ Database tables initialised")
