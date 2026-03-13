"""
State Manager for ClerKase (SQLAlchemy version)
================================================
Replaces the raw-psycopg2 implementation with a proper ORM layer.

Responsibilities
----------------
1. Load rotation templates from JSON
2. Create / retrieve / delete cases
3. Update section data and status
4. Manage clarification questions per section
5. Track flags (contradictions, gaps, warnings)
6. Store differential diagnosis evolution
7. Report progress

All cases are persisted to the database configured in DATABASE_URL.
Defaults to SQLite for local development; set DATABASE_URL to a
PostgreSQL connection string for production.
"""

import json
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from database import (
    init_db,
    SessionLocal,
    Case,
    CaseSection,
    CaseFlag,
    DifferentialDiagnosis,
    SectionStatus,
    FlagType,
    FlagSeverity,
    DifferentialPoint,
)


# ============================================================================
# HELPERS
# ============================================================================

def _get_db():
    """Return a new SQLAlchemy session. Caller is responsible for closing."""
    return SessionLocal()


# ============================================================================
# STATE MANAGER
# ============================================================================

class StateManager:
    """
    Database-backed state manager for clinical clerking cases.

    Designed as a drop-in replacement for the previous psycopg2-based
    implementation. The public API is identical so index.py needs no changes.
    """

    def __init__(self):
        self._templates: Dict[str, Dict] = {}
        self._load_templates()
        try:
            init_db()   # creates tables if they don't exist (idempotent)
        except Exception as exc:
            # Log but do NOT crash — routes that need the DB will fail individually.
            # This keeps /api/health and /api/rotations (template-only) alive.
            print(f"[ClerKase] WARNING: database init failed: {exc}", flush=True)

    # ------------------------------------------------------------------
    # TEMPLATE LOADING
    # ------------------------------------------------------------------

    def _load_templates(self):
        """Load all rotation JSON templates from the templates/ directory."""
        templates_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "templates"
        )
        rotations = [
            "paediatrics",
            "surgery",
            "internal_medicine",
            "obstetrics_gynaecology",
            "psychiatry",
            "emergency_medicine",
        ]
        for rotation in rotations:
            path = os.path.join(templates_dir, f"{rotation}.json")
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    self._templates[rotation] = json.load(f)
            else:
                print(f"⚠  Template not found: {path}")

        print(f"✓ Loaded {len(self._templates)} rotation template(s)")

    def get_template(self, rotation: str) -> Optional[Dict]:
        return self._templates.get(rotation)

    def get_available_rotations(self) -> List[str]:
        return list(self._templates.keys())

    def get_section_order(self, rotation: str) -> List[str]:
        template = self.get_template(rotation)
        if not template:
            return []
        sections = sorted(template.get("sections", []), key=lambda s: s["order"])
        return [s["name"] for s in sections]

    # ------------------------------------------------------------------
    # CASE LIFECYCLE
    # ------------------------------------------------------------------

    def create_case(self, rotation: str) -> "CaseStateProxy":
        """
        Create and persist a new case.

        Returns a CaseStateProxy (dict-like) consistent with the old API.
        """
        if rotation not in self._templates:
            raise ValueError(
                f"Unknown rotation: '{rotation}'. "
                f"Available: {', '.join(self._templates)}"
            )

        template = self._templates[rotation]
        section_order = self.get_section_order(rotation)
        if not section_order:
            raise ValueError(f"No sections defined for rotation: {rotation}")

        case_id = str(uuid.uuid4())
        now = datetime.utcnow()

        # Build initial section_status dict
        section_status = {name: SectionStatus.NOT_STARTED.value for name in section_order}
        section_status[section_order[0]] = SectionStatus.IN_PROGRESS.value

        db = _get_db()
        try:
            db_case = Case(
                case_id=case_id,
                rotation=rotation,
                template_version=template.get("version", "1.0"),
                current_section=section_order[0],
                completed_sections=[],
                section_status=section_status,
                created_at=now,
                last_updated=now,
            )
            db.add(db_case)
            db.flush()  # get db_case.id before creating sections

            # Pre-create a CaseSection row for every section
            for name in section_order:
                db.add(CaseSection(
                    case_id=db_case.id,
                    section_name=name,
                    data={},
                    status=SectionStatus.NOT_STARTED,
                    pending_clarifications=[],
                ))

            db.commit()
            db.refresh(db_case)
            return self._to_proxy(db_case)

        finally:
            db.close()

    def get_case(self, case_id: str) -> Optional["CaseStateProxy"]:
        """Return a CaseStateProxy or None if not found."""
        db = _get_db()
        try:
            db_case = db.query(Case).filter(Case.case_id == case_id).first()
            if not db_case:
                return None
            return self._to_proxy(db_case)
        finally:
            db.close()

    def delete_case(self, case_id: str) -> bool:
    session = SessionLocal()
    try:
        # IMPORTANT: We must filter by Case.case_id (the string), 
        # not Case.id (the integer)
        case = session.query(Case).filter(Case.case_id == case_id).first()
        if not case:
            print(f"Delete failed: Case {case_id} not found")
            return False
            
        session.delete(case)
        session.commit()
        print(f"✓ Case {case_id} deleted successfully")
        return True
    except Exception as e:
        session.rollback()
        print(f"Error deleting case: {e}")
        return False
    finally:
        session.close()

    def get_all_cases(self) -> List[Dict]:
        """Return a summary list of all cases, most recently updated first."""
        db = _get_db()
        try:
            rows = (
                db.query(Case)
                .order_by(Case.last_updated.desc())
                .all()
            )
            return [
                {
                    "case_id": c.case_id,
                    "rotation": c.rotation,
                    "current_section": c.current_section,
                    "is_complete": c.is_complete,
                    "created_at": c.created_at.isoformat() if c.created_at else None,
                    "last_updated": c.last_updated.isoformat() if c.last_updated else None,
                }
                for c in rows
            ]
        except Exception as e:
            print(f"Error listing cases: {e}")
            return []
        finally:
            db.close()

    # ------------------------------------------------------------------
    # SECTION DATA
    # ------------------------------------------------------------------

    def update_section(
        self,
        case_id: str,
        section_name: str,
        data: Dict[str, Any],
        status: Optional[str] = None,
    ) -> "CaseStateProxy":
        """
        Persist field data for a section.

        If status is provided it must be a SectionStatus.value string.
        """
        db = _get_db()
        try:
            db_case = self._require_case(db, case_id)
            section = self._require_section(db, db_case.id, section_name)

            section.data = data
            section.updated_at = datetime.utcnow()

            if status:
                section.status = SectionStatus(status)
                db_case.section_status = {
                    **db_case.section_status,
                    section_name: status,
                }

            db_case.last_updated = datetime.utcnow()
            db.commit()
            db.refresh(db_case)
            return self._to_proxy(db_case)

        finally:
            db.close()

    def get_section_data(self, case_id: str, section_name: str) -> Dict[str, Any]:
        """Return the stored field data for a section, or {}."""
        db = _get_db()
        try:
            db_case = self._require_case(db, case_id)
            section = self._require_section(db, db_case.id, section_name)
            return section.data or {}
        finally:
            db.close()

    # ------------------------------------------------------------------
    # CLARIFICATIONS
    # ------------------------------------------------------------------

    def add_clarifications(
        self, case_id: str, section_name: str, questions: List[str]
    ) -> "CaseStateProxy":
        """Attach clarification questions to a section."""
        db = _get_db()
        try:
            db_case = self._require_case(db, case_id)
            section = self._require_section(db, db_case.id, section_name)

            section.pending_clarifications = questions
            section.status = SectionStatus.PENDING_CLARIFICATION
            db_case.section_status = {
                **db_case.section_status,
                section_name: SectionStatus.PENDING_CLARIFICATION.value,
            }
            db_case.last_updated = datetime.utcnow()
            db.commit()
            db.refresh(db_case)
            return self._to_proxy(db_case)

        finally:
            db.close()

    def clear_clarifications(
        self, case_id: str, section_name: str
    ) -> "CaseStateProxy":
        """
        Clear pending clarifications from a section.
        Marks the section complete if it already has data, otherwise in_progress.
        """
        db = _get_db()
        try:
            db_case = self._require_case(db, case_id)
            section = self._require_section(db, db_case.id, section_name)

            section.pending_clarifications = []

            if section.data:
                new_status = SectionStatus.COMPLETE
                if section_name not in (db_case.completed_sections or []):
                    completed = list(db_case.completed_sections or [])
                    completed.append(section_name)
                    db_case.completed_sections = completed
            else:
                new_status = SectionStatus.IN_PROGRESS

            section.status = new_status
            db_case.section_status = {
                **db_case.section_status,
                section_name: new_status.value,
            }
            db_case.last_updated = datetime.utcnow()
            db.commit()
            db.refresh(db_case)
            return self._to_proxy(db_case)

        finally:
            db.close()

    # ------------------------------------------------------------------
    # WORKFLOW
    # ------------------------------------------------------------------

    def move_to_next_section(self, case_id: str) -> "CaseStateProxy":
        """
        Mark the current section complete and advance to the next one.
        Sets is_complete=True when the final section is reached.
        """
        db = _get_db()
        try:
            db_case = self._require_case(db, case_id)
            section_order = self.get_section_order(db_case.rotation)
            current = db_case.current_section

            # Mark current section complete
            section = self._require_section(db, db_case.id, current)
            section.status = SectionStatus.COMPLETE

            status_map = dict(db_case.section_status or {})
            status_map[current] = SectionStatus.COMPLETE.value
            db_case.section_status = status_map

            completed = list(db_case.completed_sections or [])
            if current not in completed:
                completed.append(current)
            db_case.completed_sections = completed

            # Advance
            try:
                idx = section_order.index(current)
            except ValueError:
                idx = -1

            if idx < len(section_order) - 1:
                db_case.current_section = section_order[idx + 1]
            else:
                db_case.is_complete = True
                db_case.completed_at = datetime.utcnow()

            db_case.last_updated = datetime.utcnow()
            db.commit()
            db.refresh(db_case)
            return self._to_proxy(db_case)

        finally:
            db.close()

    # ------------------------------------------------------------------
    # FLAGS
    # ------------------------------------------------------------------

    def add_flag(
        self,
        case_id: str,
        section_name: str,
        flag_type: str,
        severity: str,
        message: str,
    ) -> None:
        """
        Persist a flag (contradiction / critical_gap / warning).

        Parameters
        ----------
        flag_type : "contradiction" | "critical_gap" | "warning"
        severity  : "high" | "medium" | "low"
        """
        db = _get_db()
        try:
            db_case = self._require_case(db, case_id)
            db.add(CaseFlag(
                case_id=db_case.id,
                flag_type=FlagType(flag_type),
                severity=FlagSeverity(severity),
                message=message,
                section=section_name,
            ))
            db.commit()
        finally:
            db.close()

    def get_unresolved_flags(
        self, case_id: str, severity: Optional[str] = None
    ) -> List[Dict]:
        """Return all unresolved flags for a case, optionally filtered by severity."""
        db = _get_db()
        try:
            db_case = self._require_case(db, case_id)
            q = db.query(CaseFlag).filter(
                CaseFlag.case_id == db_case.id,
                CaseFlag.resolved == False,  # noqa: E712
            )
            if severity:
                q = q.filter(CaseFlag.severity == FlagSeverity(severity))
            return [f.to_dict() for f in q.all()]
        finally:
            db.close()

    def resolve_flag(self, case_id: str, flag_id: int, note: str = "") -> bool:
        """Mark a specific flag as resolved."""
        db = _get_db()
        try:
            db_case = self._require_case(db, case_id)
            flag = (
                db.query(CaseFlag)
                .filter(CaseFlag.id == flag_id, CaseFlag.case_id == db_case.id)
                .first()
            )
            if not flag:
                return False
            flag.resolved = True
            flag.resolved_at = datetime.utcnow()
            flag.resolution_note = note
            db.commit()
            return True
        finally:
            db.close()

    # ------------------------------------------------------------------
    # DIFFERENTIALS
    # ------------------------------------------------------------------

    def add_differential(
        self,
        case_id: str,
        working_diagnosis: str,
        differentials: List[Dict],
        point: str,
    ) -> None:
        """
        Store a differential diagnosis snapshot.

        Parameters
        ----------
        point : "after_history" | "after_examination"
        differentials : [{"diagnosis": "...", "justification": "..."}, ...]
        """
        db = _get_db()
        try:
            db_case = self._require_case(db, case_id)
            db.add(DifferentialDiagnosis(
                case_id=db_case.id,
                point=DifferentialPoint(point),
                working_diagnosis=working_diagnosis,
                differentials=differentials,
            ))
            db.commit()
        finally:
            db.close()

    def get_latest_differential(self, case_id: str) -> Optional[Dict]:
        db = _get_db()
        try:
            db_case = self._require_case(db, case_id)
            dd = (
                db.query(DifferentialDiagnosis)
                .filter(DifferentialDiagnosis.case_id == db_case.id)
                .order_by(DifferentialDiagnosis.created_at.desc())
                .first()
            )
            return dd.to_dict() if dd else None
        finally:
            db.close()

    def get_differential_history(self, case_id: str) -> List[Dict]:
        db = _get_db()
        try:
            db_case = self._require_case(db, case_id)
            rows = (
                db.query(DifferentialDiagnosis)
                .filter(DifferentialDiagnosis.case_id == db_case.id)
                .order_by(DifferentialDiagnosis.created_at.asc())
                .all()
            )
            return [r.to_dict() for r in rows]
        finally:
            db.close()

    # ------------------------------------------------------------------
    # PROGRESS
    # ------------------------------------------------------------------

    def get_progress(self, case_id: str) -> Dict:
        """Return structured progress summary for a case."""
        db = _get_db()
        try:
            db_case = self._require_case(db, case_id)
            section_order = self.get_section_order(db_case.rotation)
            total = len(section_order)
            completed = len(db_case.completed_sections or [])

            # Count sections with pending clarifications
            pending_clarification_count = (
                db.query(CaseSection)
                .filter(
                    CaseSection.case_id == db_case.id,
                    CaseSection.status == SectionStatus.PENDING_CLARIFICATION,
                )
                .count()
            )

            section_breakdown = {}
            for name in section_order:
                sec = (
                    db.query(CaseSection)
                    .filter(
                        CaseSection.case_id == db_case.id,
                        CaseSection.section_name == name,
                    )
                    .first()
                )
                section_breakdown[name] = {
                    "status": sec.status.value if sec else "not_started",
                    "has_clarifications": bool(
                        sec and sec.pending_clarifications
                    ),
                }

            return {
                "case_id": case_id,
                "rotation": db_case.rotation,
                "total_sections": total,
                "completed_sections": completed,
                "completion_percentage": (
                    round((completed / total) * 100, 1) if total else 0
                ),
                "current_section": db_case.current_section,
                "is_complete": db_case.is_complete,
                "pending_clarifications": pending_clarification_count,
                "section_breakdown": section_breakdown,
            }
        finally:
            db.close()

    # ------------------------------------------------------------------
    # INTERNAL HELPERS
    # ------------------------------------------------------------------

    def _require_case(self, db, case_id: str) -> Case:
        """Fetch a Case row or raise ValueError."""
        db_case = db.query(Case).filter(Case.case_id == case_id).first()
        if not db_case:
            raise ValueError(f"Case not found: {case_id}")
        return db_case

    def _require_section(self, db, case_db_id: int, section_name: str) -> CaseSection:
        """Fetch (or lazily create) a CaseSection row."""
        section = (
            db.query(CaseSection)
            .filter(
                CaseSection.case_id == case_db_id,
                CaseSection.section_name == section_name,
            )
            .first()
        )
        if not section:
            # Graceful fallback: create the row rather than crashing
            section = CaseSection(
                case_id=case_db_id,
                section_name=section_name,
                data={},
                status=SectionStatus.NOT_STARTED,
                pending_clarifications=[],
            )
            db.add(section)
            db.flush()
        return section

    def _to_proxy(self, db_case: Case) -> Dict:
        """
        Convert a SQLAlchemy Case row into a plain dict.
        Sections are included as a nested dict so index.py can
        access case["sections"]["demographics"]["data"] etc.
        """
        sections_dict = {}
        for sec in db_case.sections:
            sections_dict[sec.section_name] = {
                "section_name": sec.section_name,
                "data": sec.data or {},
                "status": sec.status.value,
                "pending_clarifications": sec.pending_clarifications or [],
            }

        return {
            "case_id": db_case.case_id,
            "rotation": db_case.rotation,
            "template_version": db_case.template_version,
            "current_section": db_case.current_section,
            "completed_sections": db_case.completed_sections or [],
            "section_status": db_case.section_status or {},
            "sections": sections_dict,
            "is_complete": db_case.is_complete,
            "created_at": db_case.created_at.isoformat() if db_case.created_at else None,
            "last_updated": db_case.last_updated.isoformat() if db_case.last_updated else None,
            "completed_at": db_case.completed_at.isoformat() if db_case.completed_at else None,
        }


# ============================================================================
# SINGLETON
# ============================================================================

_state_manager: Optional[StateManager] = None


def get_state_manager() -> StateManager:
    global _state_manager
    if _state_manager is None:
        _state_manager = StateManager()
    return _state_manager
