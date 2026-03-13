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

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///clerkase.db")
DB_ECHO = os.getenv("DB_ECHO", "false").lower() == "true"
DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "5"))
DB_MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "10"))

# ✅ Fix 1: Vercel sometimes provides "postgres://" — SQLAlchemy needs "postgresql://"
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL,
        echo=DB_ECHO,
        connect_args={"check_same_thread": False}
    )
else:
    # ✅ Fix 2: Strip ?sslmode from URL and pass SSL via connect_args instead
    connect_args = {}
    if "sslmode=require" in DATABASE_URL:
        DATABASE_URL = DATABASE_URL.replace("?sslmode=require", "").replace("&sslmode=require", "")
        connect_args["sslmode"] = "require"

    engine = create_engine(
        DATABASE_URL,
        echo=DB_ECHO,
        pool_size=DB_POOL_SIZE,
        max_overflow=DB_MAX_OVERFLOW,
        pool_pre_ping=True,
        connect_args=connect_args
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
