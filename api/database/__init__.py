"""
Database package for ClerKase.
Exports all models and session utilities from a single import point.
"""

from .models import (
    Base,
    User,
    Case,
    CaseSection,
    CaseFlag,
    DifferentialDiagnosis,
    AIUsage,
    SectionStatus,
    FlagType,
    FlagSeverity,
    DifferentialPoint,
)
from .session import (
    engine,
    SessionLocal,
    get_db,
    init_db,
)

__all__ = [
    # Models
    "Base",
    "User",
    "Case",
    "CaseSection",
    "CaseFlag",
    "DifferentialDiagnosis",
    "AIUsage",
    # Enums
    "SectionStatus",
    "FlagType",
    "FlagSeverity",
    "DifferentialPoint",
    # Session
    "engine",
    "SessionLocal",
    "get_db",
    "init_db",
]
