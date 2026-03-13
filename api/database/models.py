"""
SQLAlchemy ORM models for ClerKase.

Tables
------
users               - Student accounts
cases               - Top-level clerking cases
case_sections       - Per-section data + status
case_flags          - Contradictions / gaps / warnings
differential_diagnoses - Differential at history & exam points
ai_usage            - Token / cost tracking per API call
"""

from datetime import datetime
import enum

from sqlalchemy import (
    Boolean, Column, DateTime, Enum as SQLEnum,
    Float, ForeignKey, Integer, JSON, String, Text
)
from sqlalchemy.orm import relationship

from .session import Base


# ============================================================================
# ENUMS
# ============================================================================

class SectionStatus(enum.Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    PENDING_CLARIFICATION = "pending_clarification"
    COMPLETE = "complete"


class FlagType(enum.Enum):
    CONTRADICTION = "contradiction"
    CRITICAL_GAP = "critical_gap"
    WARNING = "warning"


class FlagSeverity(enum.Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class DifferentialPoint(enum.Enum):
    AFTER_HISTORY = "after_history"
    AFTER_EXAMINATION = "after_examination"


# ============================================================================
# USER
# ============================================================================

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    username = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255))

    # Student metadata
    institution = Column(String(255))
    year_of_study = Column(Integer)
    student_id = Column(String(100))

    # Account status
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)

    # Subscription tier (free / student / institution)
    subscription_tier = Column(String(50), default="free")
    subscription_expires_at = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_login = Column(DateTime, nullable=True)

    # Relationships
    cases = relationship("Case", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User {self.username}>"

    def to_dict(self):
        return {
            "id": self.id,
            "email": self.email,
            "username": self.username,
            "full_name": self.full_name,
            "institution": self.institution,
            "year_of_study": self.year_of_study,
            "student_id": self.student_id,
            "is_active": self.is_active,
            "subscription_tier": self.subscription_tier,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_login": self.last_login.isoformat() if self.last_login else None,
        }


# ============================================================================
# CASE
# ============================================================================

class Case(Base):
    __tablename__ = "cases"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(String(255), unique=True, index=True, nullable=False)

    # Owner (nullable until auth is required for all routes)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Case metadata
    rotation = Column(String(100), nullable=False, index=True)
    template_version = Column(String(20), default="1.0")

    # Workflow state
    current_section = Column(String(100), nullable=False)
    completed_sections = Column(JSON, default=list)   # ["demographics", "hpc", ...]
    section_status = Column(JSON, default=dict)        # {"demographics": "complete", ...}

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Completion
    is_complete = Column(Boolean, default=False)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", back_populates="cases")
    sections = relationship("CaseSection", back_populates="case", cascade="all, delete-orphan")
    flags = relationship("CaseFlag", back_populates="case", cascade="all, delete-orphan")
    differentials = relationship("DifferentialDiagnosis", back_populates="case", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Case {self.case_id} ({self.rotation})>"

    def to_dict(self, include_sections=False):
        d = {
            "case_id": self.case_id,
            "rotation": self.rotation,
            "template_version": self.template_version,
            "current_section": self.current_section,
            "completed_sections": self.completed_sections or [],
            "section_status": self.section_status or {},
            "is_complete": self.is_complete,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }
        if include_sections:
            d["sections"] = {s.section_name: s.to_dict() for s in self.sections}
        return d


# ============================================================================
# CASE SECTION
# ============================================================================

class CaseSection(Base):
    __tablename__ = "case_sections"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False)

    section_name = Column(String(100), nullable=False, index=True)
    data = Column(JSON, default=dict)   # All field values for this section

    status = Column(
        SQLEnum(SectionStatus),
        default=SectionStatus.NOT_STARTED,
        nullable=False
    )

    # Outstanding clarification questions
    pending_clarifications = Column(JSON, default=list)  # ["Question 1", ...]

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    case = relationship("Case", back_populates="sections")

    def __repr__(self):
        return f"<CaseSection {self.section_name} [{self.status.value}]>"

    def to_dict(self):
        return {
            "section_name": self.section_name,
            "data": self.data or {},
            "status": self.status.value,
            "pending_clarifications": self.pending_clarifications or [],
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


# ============================================================================
# CASE FLAG
# ============================================================================

class CaseFlag(Base):
    __tablename__ = "case_flags"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False)

    flag_type = Column(SQLEnum(FlagType), nullable=False)
    severity = Column(SQLEnum(FlagSeverity), nullable=False)
    message = Column(Text, nullable=False)
    section = Column(String(100), nullable=False)

    # Resolution tracking
    resolved = Column(Boolean, default=False)
    resolved_at = Column(DateTime, nullable=True)
    resolution_note = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    case = relationship("Case", back_populates="flags")

    def __repr__(self):
        return f"<CaseFlag {self.flag_type.value} ({self.severity.value})>"

    def to_dict(self):
        return {
            "id": self.id,
            "flag_type": self.flag_type.value,
            "severity": self.severity.value,
            "message": self.message,
            "section": self.section,
            "resolved": self.resolved,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ============================================================================
# DIFFERENTIAL DIAGNOSIS
# ============================================================================

class DifferentialDiagnosis(Base):
    __tablename__ = "differential_diagnoses"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False)

    point = Column(SQLEnum(DifferentialPoint), nullable=False)
    working_diagnosis = Column(Text, nullable=False)
    differentials = Column(JSON, default=list)
    # Format: [{"diagnosis": "...", "justification": "..."}, ...]

    created_at = Column(DateTime, default=datetime.utcnow)

    case = relationship("Case", back_populates="differentials")

    def __repr__(self):
        return f"<DifferentialDiagnosis {self.point.value} for case {self.case_id}>"

    def to_dict(self):
        return {
            "point": self.point.value,
            "working_diagnosis": self.working_diagnosis,
            "differentials": self.differentials or [],
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ============================================================================
# AI USAGE TRACKING
# ============================================================================

class AIUsage(Base):
    __tablename__ = "ai_usage"

    id = Column(Integer, primary_key=True, index=True)

    case_id = Column(String(255), index=True)
    section = Column(String(100))
    operation = Column(String(100))   # e.g. "clarification", "differential"

    input_tokens = Column(Integer, nullable=False)
    output_tokens = Column(Integer, nullable=False)
    cost_usd = Column(Float, nullable=False)
    cache_hit = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    def __repr__(self):
        return f"<AIUsage ${self.cost_usd:.4f} ({self.input_tokens + self.output_tokens} tokens)>"

    def to_dict(self):
        return {
            "case_id": self.case_id,
            "section": self.section,
            "operation": self.operation,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cost_usd": self.cost_usd,
            "cache_hit": self.cache_hit,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
