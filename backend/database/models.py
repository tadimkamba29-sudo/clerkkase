"""
SQLAlchemy database models for ClerKase
"""

from sqlalchemy import (
    Column, Integer, String, Text, Boolean, Float, DateTime, 
    ForeignKey, Enum as SQLEnum, JSON
)
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from .session import Base


# ============================================================================
# ENUMS
# ============================================================================

class SectionStatus(enum.Enum):
    """Section completion status"""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    PENDING_CLARIFICATION = "pending_clarification"
    COMPLETE = "complete"


class FlagType(enum.Enum):
    """Flag/contradiction types"""
    CONTRADICTION = "contradiction"
    CRITICAL_GAP = "critical_gap"
    WARNING = "warning"


class FlagSeverity(enum.Enum):
    """Flag severity levels"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class DifferentialPoint(enum.Enum):
    """When differential was generated"""
    AFTER_HISTORY = "after_history"
    AFTER_EXAMINATION = "after_examination"


# ============================================================================
# MODELS
# ============================================================================

class User(Base):
    """
    User model (for future authentication)
    """
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    username = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255))
    
    # User metadata
    institution = Column(String(255))
    year_of_study = Column(Integer)
    student_id = Column(String(100))
    
    # Account status
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    
    # Subscription (for future payment system)
    subscription_tier = Column(String(50), default="free")  # free, student, institution
    subscription_expires_at = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_login = Column(DateTime, nullable=True)
    
    # Relationships
    cases = relationship("Case", back_populates="user", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User {self.username}>"


class Case(Base):
    """
    Clinical case model
    """
    __tablename__ = "cases"
    
    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(String(255), unique=True, index=True, nullable=False)
    
    # User relationship (nullable for now, will be required after auth)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # Case metadata
    rotation = Column(String(100), nullable=False, index=True)
    template_version = Column(String(20), default="1.0")
    
    # Workflow state
    current_section = Column(String(100), nullable=False)
    completed_sections = Column(JSON, default=list)  # List of section names
    section_status = Column(JSON, default=dict)  # {section_name: status}
    
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


class CaseSection(Base):
    """
    Individual section data for a case
    """
    __tablename__ = "case_sections"
    
    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False)
    
    # Section identification
    section_name = Column(String(100), nullable=False, index=True)
    
    # Section data (stored as JSON)
    data = Column(JSON, default=dict)
    
    # Section metadata
    status = Column(SQLEnum(SectionStatus), default=SectionStatus.NOT_STARTED)
    
    # Clarifications
    pending_clarifications = Column(JSON, default=list)  # List of question strings
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    case = relationship("Case", back_populates="sections")
    
    def __repr__(self):
        return f"<CaseSection {self.section_name} for Case {self.case_id}>"


class CaseFlag(Base):
    """
    Flags (contradictions, gaps, warnings) for a case
    """
    __tablename__ = "case_flags"
    
    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False)
    
    # Flag details
    flag_type = Column(SQLEnum(FlagType), nullable=False)
    severity = Column(SQLEnum(FlagSeverity), nullable=False)
    message = Column(Text, nullable=False)
    section = Column(String(100), nullable=False)
    
    # Resolution
    resolved = Column(Boolean, default=False)
    resolved_at = Column(DateTime, nullable=True)
    resolution_note = Column(Text, nullable=True)
    
    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    case = relationship("Case", back_populates="flags")
    
    def __repr__(self):
        return f"<CaseFlag {self.flag_type.value} ({self.severity.value})>"


class DifferentialDiagnosis(Base):
    """
    Differential diagnosis at a specific point
    """
    __tablename__ = "differential_diagnoses"
    
    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False)
    
    # Differential details
    point = Column(SQLEnum(DifferentialPoint), nullable=False)
    working_diagnosis = Column(Text, nullable=False)
    differentials = Column(JSON, default=list)  # List of {diagnosis, justification}
    
    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    case = relationship("Case", back_populates="differentials")
    
    def __repr__(self):
        return f"<DifferentialDiagnosis for Case {self.case_id} ({self.point.value})>"


class AIUsage(Base):
    """
    Track AI API usage for cost monitoring
    """
    __tablename__ = "ai_usage"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Usage details
    case_id = Column(String(255), index=True)
    section = Column(String(100))
    
    # Token usage
    input_tokens = Column(Integer, nullable=False)
    output_tokens = Column(Integer, nullable=False)
    
    # Cost
    cost_usd = Column(Float, nullable=False)
    
    # Cache
    cache_hit = Column(Boolean, default=False)
    
    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    def __repr__(self):
        return f"<AIUsage ${self.cost_usd:.4f} ({self.input_tokens + self.output_tokens} tokens)>"
