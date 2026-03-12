"""
State Manager for ClerKase
Manages case state, progress tracking, and workflow
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum
import uuid


class SectionStatus(Enum):
    """Section completion status"""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    PENDING_CLARIFICATION = "pending_clarification"
    COMPLETE = "complete"


@dataclass
class SectionData:
    """Data for a single section"""
    section_name: str
    data: Dict[str, Any]
    status: str = "not_started"
    pending_clarifications: List[str] = None
    
    def __post_init__(self):
        if self.pending_clarifications is None:
            self.pending_clarifications = []


@dataclass
class CaseState:
    """Complete case state"""
    case_id: str
    rotation: str
    template_version: str
    current_section: str
    completed_sections: List[str]
    section_status: Dict[str, str]
    sections: Dict[str, SectionData]
    created_at: str
    last_updated: str
    is_complete: bool = False
    completed_at: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return {
            "case_id": self.case_id,
            "rotation": self.rotation,
            "template_version": self.template_version,
            "current_section": self.current_section,
            "completed_sections": self.completed_sections,
            "section_status": self.section_status,
            "sections": {
                name: {
                    "section_name": s.section_name,
                    "data": s.data,
                    "status": s.status,
                    "pending_clarifications": s.pending_clarifications
                } for name, s in self.sections.items()
            },
            "created_at": self.created_at,
            "last_updated": self.last_updated,
            "is_complete": self.is_complete,
            "completed_at": self.completed_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'CaseState':
        """Create CaseState from dictionary"""
        sections = {}
        for name, s_data in data.get("sections", {}).items():
            sections[name] = SectionData(
                section_name=s_data["section_name"],
                data=s_data.get("data", {}),
                status=s_data.get("status", "not_started"),
                pending_clarifications=s_data.get("pending_clarifications", [])
            )
        
        return cls(
            case_id=data["case_id"],
            rotation=data["rotation"],
            template_version=data.get("template_version", "1.0"),
            current_section=data["current_section"],
            completed_sections=data.get("completed_sections", []),
            section_status=data.get("section_status", {}),
            sections=sections,
            created_at=data["created_at"],
            last_updated=data["last_updated"],
            is_complete=data.get("is_complete", False),
            completed_at=data.get("completed_at")
        )


class StateManager:
    """
    Manages case state and workflow
    """
    
    def __init__(self, storage_dir: str = "case_storage"):
        self.storage_dir = storage_dir
        self._ensure_storage_dir()
        self._templates = {}
        self._load_templates()
    
    def _ensure_storage_dir(self):
        """Ensure storage directory exists"""
        if not os.path.exists(self.storage_dir):
            os.makedirs(self.storage_dir)
    
    def _load_templates(self):
        """Load all rotation templates"""
        templates_dir = os.path.join(os.path.dirname(__file__), "templates")
        
        rotations = [
            "paediatrics",
            "surgery", 
            "internal_medicine",
            "obstetrics_gynaecology",
            "psychiatry",
            "emergency_medicine"
        ]
        
        for rotation in rotations:
            template_path = os.path.join(templates_dir, f"{rotation}.json")
            if os.path.exists(template_path):
                with open(template_path, 'r') as f:
                    self._templates[rotation] = json.load(f)
    
    def get_template(self, rotation: str) -> Optional[Dict]:
        """Get template for a rotation"""
        return self._templates.get(rotation)
    
    def get_available_rotations(self) -> List[str]:
        """Get list of available rotations"""
        return list(self._templates.keys())
    
    def get_section_order(self, rotation: str) -> List[str]:
        """Get ordered list of section names for a rotation"""
        template = self.get_template(rotation)
        if not template:
            return []
        
        sections = sorted(template["sections"], key=lambda s: s["order"])
        return [s["name"] for s in sections]
    
    def create_case(self, rotation: str) -> CaseState:
        """
        Create a new case
        
        Args:
            rotation: The rotation type
            
        Returns:
            New CaseState object
        """
        if rotation not in self._templates:
            raise ValueError(f"Unknown rotation: {rotation}")
        
        template = self._templates[rotation]
        section_order = self.get_section_order(rotation)
        
        if not section_order:
            raise ValueError(f"No sections found for rotation: {rotation}")
        
        # Initialize sections
        sections = {}
        section_status = {}
        for section_name in section_order:
            sections[section_name] = SectionData(
                section_name=section_name,
                data={},
                status=SectionStatus.NOT_STARTED.value,
                pending_clarifications=[]
            )
            section_status[section_name] = SectionStatus.NOT_STARTED.value
        
        now = datetime.utcnow().isoformat()
        
        case_state = CaseState(
            case_id=str(uuid.uuid4()),
            rotation=rotation,
            template_version=template.get("version", "1.0"),
            current_section=section_order[0],
            completed_sections=[],
            section_status=section_status,
            sections=sections,
            created_at=now,
            last_updated=now
        )
        
        # Save to storage
        self._save_case(case_state)
        
        return case_state
    
    def get_case(self, case_id: str) -> Optional[CaseState]:
        """
        Retrieve a case by ID
        
        Args:
            case_id: The case ID
            
        Returns:
            CaseState if found, None otherwise
        """
        case_path = os.path.join(self.storage_dir, f"{case_id}.json")
        
        if not os.path.exists(case_path):
            return None
        
        try:
            with open(case_path, 'r') as f:
                data = json.load(f)
            return CaseState.from_dict(data)
        except Exception as e:
            print(f"Error loading case {case_id}: {e}")
            return None
    
    def _save_case(self, case_state: CaseState):
        """Save case state to storage"""
        case_path = os.path.join(self.storage_dir, f"{case_state.case_id}.json")
        
        with open(case_path, 'w') as f:
            json.dump(case_state.to_dict(), f, indent=2)
    
    def update_section(
        self,
        case_id: str,
        section_name: str,
        data: Dict[str, Any],
        status: Optional[str] = None
    ) -> CaseState:
        """
        Update a section with new data
        
        Args:
            case_id: The case ID
            section_name: Section to update
            data: New section data
            status: Optional new status
            
        Returns:
            Updated CaseState
        """
        case_state = self.get_case(case_id)
        if not case_state:
            raise ValueError(f"Case not found: {case_id}")
        
        if section_name not in case_state.sections:
            raise ValueError(f"Section not found: {section_name}")
        
        # Update section data
        section = case_state.sections[section_name]
        section.data = data
        
        if status:
            section.status = status
            case_state.section_status[section_name] = status
        
        case_state.last_updated = datetime.utcnow().isoformat()
        
        # Save updated case
        self._save_case(case_state)
        
        return case_state
    
    def add_clarifications(
        self,
        case_id: str,
        section_name: str,
        questions: List[str]
    ) -> CaseState:
        """
        Add clarification questions to a section
        
        Args:
            case_id: The case ID
            section_name: Section to update
            questions: List of clarification questions
            
        Returns:
            Updated CaseState
        """
        case_state = self.get_case(case_id)
        if not case_state:
            raise ValueError(f"Case not found: {case_id}")
        
        if section_name not in case_state.sections:
            raise ValueError(f"Section not found: {section_name}")
        
        section = case_state.sections[section_name]
        section.pending_clarifications = questions
        section.status = SectionStatus.PENDING_CLARIFICATION.value
        case_state.section_status[section_name] = SectionStatus.PENDING_CLARIFICATION.value
        
        case_state.last_updated = datetime.utcnow().isoformat()
        
        self._save_case(case_state)
        
        return case_state
    
    def clear_clarifications(self, case_id: str, section_name: str) -> CaseState:
        """
        Clear clarification questions from a section
        
        Args:
            case_id: The case ID
            section_name: Section to update
            
        Returns:
            Updated CaseState
        """
        case_state = self.get_case(case_id)
        if not case_state:
            raise ValueError(f"Case not found: {case_id}")
        
        if section_name not in case_state.sections:
            raise ValueError(f"Section not found: {section_name}")
        
        section = case_state.sections[section_name]
        section.pending_clarifications = []
        
        # If section has data, mark as complete, otherwise in_progress
        if section.data:
            section.status = SectionStatus.COMPLETE.value
            case_state.section_status[section_name] = SectionStatus.COMPLETE.value
            if section_name not in case_state.completed_sections:
                case_state.completed_sections.append(section_name)
        else:
            section.status = SectionStatus.IN_PROGRESS.value
            case_state.section_status[section_name] = SectionStatus.IN_PROGRESS.value
        
        case_state.last_updated = datetime.utcnow().isoformat()
        
        self._save_case(case_state)
        
        return case_state
    
    def move_to_next_section(self, case_id: str) -> CaseState:
        """
        Move to the next section in the workflow
        
        Args:
            case_id: The case ID
            
        Returns:
            Updated CaseState
        """
        case_state = self.get_case(case_id)
        if not case_state:
            raise ValueError(f"Case not found: {case_id}")
        
        section_order = self.get_section_order(case_state.rotation)
        current_idx = section_order.index(case_state.current_section)
        
        # Mark current section as complete if not already
        current_section = case_state.sections[case_state.current_section]
        if current_section.status != SectionStatus.COMPLETE.value:
            current_section.status = SectionStatus.COMPLETE.value
            case_state.section_status[case_state.current_section] = SectionStatus.COMPLETE.value
            if case_state.current_section not in case_state.completed_sections:
                case_state.completed_sections.append(case_state.current_section)
        
        # Move to next section
        if current_idx < len(section_order) - 1:
            case_state.current_section = section_order[current_idx + 1]
        else:
            # All sections complete
            case_state.is_complete = True
            case_state.completed_at = datetime.utcnow().isoformat()
        
        case_state.last_updated = datetime.utcnow().isoformat()
        
        self._save_case(case_state)
        
        return case_state
    
    def get_progress(self, case_id: str) -> Dict:
        """
        Get progress summary for a case
        
        Args:
            case_id: The case ID
            
        Returns:
            Progress summary dictionary
        """
        case_state = self.get_case(case_id)
        if not case_state:
            raise ValueError(f"Case not found: {case_id}")
        
        section_order = self.get_section_order(case_state.rotation)
        total_sections = len(section_order)
        completed = len(case_state.completed_sections)
        
        # Count sections with clarifications
        pending_clarifications = sum(
            1 for s in case_state.sections.values()
            if s.pending_clarifications
        )
        
        return {
            "case_id": case_id,
            "rotation": case_state.rotation,
            "total_sections": total_sections,
            "completed_sections": completed,
            "completion_percentage": round((completed / total_sections) * 100, 1),
            "current_section": case_state.current_section,
            "is_complete": case_state.is_complete,
            "pending_clarifications": pending_clarifications,
            "section_breakdown": {
                name: {
                    "status": case_state.section_status.get(name, "not_started"),
                    "has_clarifications": bool(
                        case_state.sections.get(name, SectionData("", {})).pending_clarifications
                    )
                } for name in section_order
            }
        }
    
    def get_all_cases(self) -> List[Dict]:
        """
        Get summary of all cases
        
        Returns:
            List of case summaries
        """
        cases = []
        
        if not os.path.exists(self.storage_dir):
            return cases
        
        for filename in os.listdir(self.storage_dir):
            if filename.endswith('.json'):
                case_id = filename[:-5]  # Remove .json
                case_state = self.get_case(case_id)
                if case_state:
                    cases.append({
                        "case_id": case_state.case_id,
                        "rotation": case_state.rotation,
                        "current_section": case_state.current_section,
                        "is_complete": case_state.is_complete,
                        "created_at": case_state.created_at,
                        "last_updated": case_state.last_updated
                    })
        
        return sorted(cases, key=lambda c: c["created_at"], reverse=True)
    
    def delete_case(self, case_id: str) -> bool:
        """
        Delete a case
        
        Args:
            case_id: The case ID
            
        Returns:
            True if deleted, False if not found
        """
        case_path = os.path.join(self.storage_dir, f"{case_id}.json")
        
        if os.path.exists(case_path):
            os.remove(case_path)
            return True
        
        return False


# Singleton instance
_state_manager = None


def get_state_manager() -> StateManager:
    """Get or create StateManager singleton"""
    global _state_manager
    if _state_manager is None:
        _state_manager = StateManager()
    return _state_manager
