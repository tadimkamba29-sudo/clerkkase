"""
Database session management
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get database URL from environment
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///clerkase.db")
DB_ECHO = os.getenv("DB_ECHO", "false").lower() == "true"
DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "5"))
DB_MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "10"))

# Create engine
if DATABASE_URL.startswith("sqlite"):
    # SQLite specific settings
    engine = create_engine(
        DATABASE_URL,
        echo=DB_ECHO,
        connect_args={"check_same_thread": False}  # Needed for SQLite
    )
else:
    # PostgreSQL settings
    engine = create_engine(
        DATABASE_URL,
        echo=DB_ECHO,
        pool_size=DB_POOL_SIZE,
        max_overflow=DB_MAX_OVERFLOW,
        pool_pre_ping=True  # Verify connections before using
    )

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


def get_db():
    """
    Dependency for getting database session
    Use in Flask routes with context manager
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Initialize database (create all tables)
    Run this once at application startup
    """
    from .models import Base  # Import here to avoid circular imports
    Base.metadata.create_all(bind=engine)
    print("✓ Database initialized")
