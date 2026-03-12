"""
Input Parser for ClerKase
Parses clinical input, extracts entities, and identifies SOCRATES pain
"""

import re
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime


@dataclass
class ParsedEntity:
    """A parsed entity from clinical input"""
    entity_type: str
    value: Any
    confidence: float
    position: Tuple[int, int]


@dataclass
class SocratesPain:
    """SOCRATES pain assessment"""
    site: Optional[str] = None
    onset: Optional[str] = None
    character: Optional[str] = None
    radiation: Optional[str] = None
    associations: Optional[str] = None
    time_course: Optional[str] = None
    exacerbating: Optional[str] = None
    relieving: Optional[str] = None
    severity: Optional[str] = None
    
    def is_complete(self) -> bool:
        """Check if all SOCRATES elements are present"""
        return all([
            self.site, self.onset, self.character, self.radiation,
            self.associations, self.time_course, self.exacerbating,
            self.relieving, self.severity
        ])
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "site": self.site,
            "onset": self.onset,
            "character": self.character,
            "radiation": self.radiation,
            "associations": self.associations,
            "time_course": self.time_course,
            "exacerbating": self.exacerbating,
            "relieving": self.relieving,
            "severity": self.severity,
            "is_complete": self.is_complete()
        }


class InputParser:
    """
    Parses clinical input text and extracts structured information
    """
    
    # Common symptoms for pattern matching
    SYMPTOM_PATTERNS = [
        r'\b(pain|ache|discomfort|soreness)\b',
        r'\b(fever|temperature)\b',
        r'\b(cough|shortness of breath|dyspnoea)\b',
        r'\b(nausea|vomiting|diarrhoea|constipation)\b',
        r'\b(headache|dizziness|syncope)\b',
        r'\b(rash|itching|swelling)\b',
        r'\b(fatigue|tiredness|weakness)\b',
        r'\b(loss of appetite|weight loss|weight gain)\b'
    ]
    
    # Duration patterns
    DURATION_PATTERNS = [
        r'\b(\d+)\s*(day|days|d)\b',
        r'\b(\d+)\s*(week|weeks|w)\b',
        r'\b(\d+)\s*(month|months|m)\b',
        r'\b(\d+)\s*(year|years|y)\b',
        r'\b(\d+)\s*(hour|hours|hr|hrs)\b',
        r'\b(\d+)\s*(minute|minutes|min|mins)\b',
        r'\b(since|for)\s+(.+?)(?:\.|,|;|$)',
    ]
    
    # Age patterns
    AGE_PATTERNS = [
        r'\b(\d+)\s*(?:year|yr)s?\s*old\b',
        r'\bage\s*(?:of\s*)?(\d+)\b',
        r'\b(\d+)[-\s]?(?:year|yr)[-\s]?old\b',
        r'\b(\d+)\s*y\.?o\.?\b',
    ]
    
    # Severity patterns
    SEVERITY_PATTERNS = [
        r'\b(\d+)/10\b',
        r'\b(severe|moderate|mild)\s+(?:pain|discomfort)\b',
        r'\bpain\s+(?:is\s+)?(severe|moderate|mild)\b',
        r'\b(unbearable|excruciating|intense)\b',
    ]
    
    # Medication patterns
    MEDICATION_PATTERNS = [
        r'\b(taking|on)\s+(.+?)(?:\.|,|;|$)',
        r'\b(medications?|drugs?|tablets?)\s*:?\s*(.+?)(?:\.|,|;|$)',
    ]
    
    # Allergy patterns
    ALLERGY_PATTERNS = [
        r'\ballerg(?:y|ic|ies)\s+(?:to\s+)?(.+?)(?:\.|,|;|$)',
        r'\ballergic\s+to\s+(.+?)(?:\.|,|;|$)',
    ]
    
    def __init__(self):
        self._compile_patterns()
    
    def _compile_patterns(self):
        """Compile regex patterns for efficiency"""
        self._symptom_regex = [re.compile(p, re.IGNORECASE) for p in self.SYMPTOM_PATTERNS]
        self._duration_regex = [re.compile(p, re.IGNORECASE) for p in self.DURATION_PATTERNS]
        self._age_regex = [re.compile(p, re.IGNORECASE) for p in self.AGE_PATTERNS]
        self._severity_regex = [re.compile(p, re.IGNORECASE) for p in self.SEVERITY_PATTERNS]
        self._medication_regex = [re.compile(p, re.IGNORECASE) for p in self.MEDICATION_PATTERNS]
        self._allergy_regex = [re.compile(p, re.IGNORECASE) for p in self.ALLERGY_PATTERNS]
    
    def parse(self, text: str, section_name: str) -> Dict[str, Any]:
        """
        Parse clinical input text
        
        Args:
            text: The input text to parse
            section_name: The section being parsed
            
        Returns:
            Dictionary with extracted entities and metadata
        """
        result = {
            "original_text": text,
            "section": section_name,
            "entities": [],
            "parsed_at": datetime.utcnow().isoformat()
        }
        
        # Extract entities based on section
        if section_name in ["presenting_complaint", "history_presenting_complaint"]:
            result["symptoms"] = self._extract_symptoms(text)
            result["duration"] = self._extract_duration(text)
            result["severity"] = self._extract_severity(text)
            result["socrates_pain"] = self._extract_socrates_pain(text)
        
        elif section_name == "demographics":
            result["age"] = self._extract_age(text)
        
        elif section_name == "drug_history":
            result["medications"] = self._extract_medications(text)
            result["allergies"] = self._extract_allergies(text)
        
        # Extract all entities
        result["entities"] = self._extract_all_entities(text)
        
        return result
    
    def _extract_symptoms(self, text: str) -> List[Dict]:
        """Extract symptoms from text"""
        symptoms = []
        
        for pattern in self._symptom_regex:
            matches = pattern.finditer(text)
            for match in matches:
                symptoms.append({
                    "symptom": match.group(0),
                    "position": (match.start(), match.end()),
                    "context": text[max(0, match.start()-20):min(len(text), match.end()+20)]
                })
        
        return symptoms
    
    def _extract_duration(self, text: str) -> Optional[Dict]:
        """Extract duration information"""
        for pattern in self._duration_regex:
            match = pattern.search(text)
            if match:
                return {
                    "value": match.group(0),
                    "position": (match.start(), match.end())
                }
        return None
    
    def _extract_age(self, text: str) -> Optional[Dict]:
        """Extract age information"""
        for pattern in self._age_regex:
            match = pattern.search(text)
            if match:
                age_value = match.group(1)
                return {
                    "value": int(age_value),
                    "position": (match.start(), match.end())
                }
        return None
    
    def _extract_severity(self, text: str) -> Optional[Dict]:
        """Extract severity information"""
        for pattern in self._severity_regex:
            match = pattern.search(text)
            if match:
                return {
                    "value": match.group(0),
                    "position": (match.start(), match.end())
                }
        return None
    
    def _extract_medications(self, text: str) -> List[Dict]:
        """Extract medication information"""
        medications = []
        
        for pattern in self._medication_regex:
            matches = pattern.finditer(text)
            for match in matches:
                medications.append({
                    "medication": match.group(0),
                    "position": (match.start(), match.end())
                })
        
        return medications
    
    def _extract_allergies(self, text: str) -> List[Dict]:
        """Extract allergy information"""
        allergies = []
        
        for pattern in self._allergy_regex:
            matches = pattern.finditer(text)
            for match in matches:
                allergies.append({
                    "allergen": match.group(1) if len(match.groups()) > 0 else match.group(0),
                    "position": (match.start(), match.end())
                })
        
        return allergies
    
    def _extract_socrates_pain(self, text: str) -> Optional[SocratesPain]:
        """
        Extract SOCRATES pain assessment from text
        
        SOCRATES:
        - Site: Where is the pain?
        - Onset: When did it start?
        - Character: What is it like?
        - Radiation: Does it go anywhere?
        - Associations: Any other symptoms?
        - Time course: Getting better/worse?
        - Exacerbating: What makes it worse?
        - Relieving: What makes it better?
        - Severity: How bad is it?
        """
        pain = SocratesPain()
        text_lower = text.lower()
        
        # Site patterns
        site_patterns = [
            r'(?:pain|ache)\s+(?:in|at)\s+(?:the\s+)?(.+?)(?:\.|,|;|$|\s+which)',
            r'(.+?)\s+(?:pain|ache|discomfort)',
            r'site\s*:?\s*(.+?)(?:\.|,|;|$)',
            r'location\s*:?\s*(.+?)(?:\.|,|;|$)',
        ]
        for pattern in site_patterns:
            match = re.search(pattern, text_lower)
            if match:
                pain.site = match.group(1).strip().title()
                break
        
        # Onset patterns
        onset_patterns = [
            r'(?:started|began|onset)\s+(?:on|at)?\s*(.+?)(?:\.|,|;|$)',
            r'(?:for|since)\s+(.+?)(?:\.|,|;|$)',
            r'onset\s*:?\s*(.+?)(?:\.|,|;|$)',
        ]
        for pattern in onset_patterns:
            match = re.search(pattern, text_lower)
            if match:
                pain.onset = match.group(1).strip().capitalize()
                break
        
        # Character patterns
        character_patterns = [
            r'(?:described\s+as|like\s+a|character)\s+(.+?)(?:\.|,|;|$)',
            r'\b(sharp|dull|aching|burning|stabbing|throbbing|cramping|colicky)\b',
            r'character\s*:?\s*(.+?)(?:\.|,|;|$)',
        ]
        for pattern in character_patterns:
            match = re.search(pattern, text_lower)
            if match:
                pain.character = match.group(1).strip().capitalize()
                break
        
        # Radiation patterns
        radiation_patterns = [
            r'(?:radiat|spread|move)\w*\s+(?:to|into|towards)\s+(.+?)(?:\.|,|;|$)',
            r'radiation\s*:?\s*(.+?)(?:\.|,|;|$)',
        ]
        for pattern in radiation_patterns:
            match = re.search(pattern, text_lower)
            if match:
                pain.radiation = match.group(1).strip().capitalize()
                break
        
        # Associations patterns
        associations_patterns = [
            r'(?:associated\s+with|along\s+with|also\s+has)\s+(.+?)(?:\.|,|;|$)',
            r'associations\s*:?\s*(.+?)(?:\.|,|;|$)',
        ]
        for pattern in associations_patterns:
            match = re.search(pattern, text_lower)
            if match:
                pain.associations = match.group(1).strip().capitalize()
                break
        
        # Time course patterns
        time_patterns = [
            r'(?:getting|becoming)\s+(better|worse|improving|deteriorating)',
            r'(?:constant|intermittent|comes\s+and\s+goes)',
            r'time\s+course\s*:?\s*(.+?)(?:\.|,|;|$)',
        ]
        for pattern in time_patterns:
            match = re.search(pattern, text_lower)
            if match:
                pain.time_course = match.group(0).strip().capitalize()
                break
        
        # Exacerbating patterns
        exacerbating_patterns = [
            r'(?:worse\s+with|exacerbat\w+\s+by|triggered\s+by)\s+(.+?)(?:\.|,|;|$)',
            r'exacerbating\s*:?\s*(.+?)(?:\.|,|;|$)',
        ]
        for pattern in exacerbating_patterns:
            match = re.search(pattern, text_lower)
            if match:
                pain.exacerbating = match.group(1).strip().capitalize()
                break
        
        # Relieving patterns
        relieving_patterns = [
            r'(?:better\s+with|relieved\s+by|improved\s+with)\s+(.+?)(?:\.|,|;|$)',
            r'relieving\s*:?\s*(.+?)(?:\.|,|;|$)',
        ]
        for pattern in relieving_patterns:
            match = re.search(pattern, text_lower)
            if match:
                pain.relieving = match.group(1).strip().capitalize()
                break
        
        # Severity patterns
        severity_patterns = [
            r'\b(\d+)/10\b',
            r'(?:severity|pain\s+is)\s*:?\s*(\d+)\s*/\s*10',
            r'\b(severe|moderate|mild)\s+(?:pain|discomfort)',
        ]
        for pattern in severity_patterns:
            match = re.search(pattern, text_lower)
            if match:
                pain.severity = match.group(0).strip()
                break
        
        # Return None if no pain information found
        if not any([
            pain.site, pain.onset, pain.character, pain.radiation,
            pain.associations, pain.time_course, pain.exacerbating,
            pain.relieving, pain.severity
        ]):
            return None
        
        return pain
    
    def _extract_all_entities(self, text: str) -> List[ParsedEntity]:
        """Extract all entities from text"""
        entities = []
        
        # Extract symptoms
        for pattern in self._symptom_regex:
            for match in pattern.finditer(text):
                entities.append(ParsedEntity(
                    entity_type="symptom",
                    value=match.group(0),
                    confidence=0.8,
                    position=(match.start(), match.end())
                ))
        
        # Extract durations
        for pattern in self._duration_regex:
            for match in pattern.finditer(text):
                entities.append(ParsedEntity(
                    entity_type="duration",
                    value=match.group(0),
                    confidence=0.9,
                    position=(match.start(), match.end())
                ))
        
        # Extract age
        for pattern in self._age_regex:
            for match in pattern.finditer(text):
                entities.append(ParsedEntity(
                    entity_type="age",
                    value=int(match.group(1)),
                    confidence=0.95,
                    position=(match.start(), match.end())
                ))
        
        # Extract severity
        for pattern in self._severity_regex:
            for match in pattern.finditer(text):
                entities.append(ParsedEntity(
                    entity_type="severity",
                    value=match.group(0),
                    confidence=0.85,
                    position=(match.start(), match.end())
                ))
        
        # Convert to dicts for JSON serialization
        return [
            {
                "entity_type": e.entity_type,
                "value": e.value,
                "confidence": e.confidence,
                "position": e.position
            }
            for e in entities
        ]
    
    def check_completeness(self, text: str, section_name: str, template: Dict) -> List[str]:
        """
        Check if section input is complete based on template rules
        
        Args:
            text: The input text
            section_name: The section name
            template: The rotation template
            
        Returns:
            List of missing required fields
        """
        missing = []
        
        # Find section in template
        section_template = None
        for section in template.get("sections", []):
            if section["name"] == section_name:
                section_template = section
                break
        
        if not section_template:
            return missing
        
        # Check clarification rules
        rules = section_template.get("clarification_rules", {})
        
        for field, rule in rules.items():
            # Check if field content is present
            if field == "age":
                if not self._extract_age(text):
                    missing.append(rule.get("missing", f"Missing {field}"))
            elif field == "duration":
                if not self._extract_duration(text):
                    missing.append(rule.get("missing", f"Missing {field}"))
            elif field == "weight":
                # Check for weight in text
                weight_pattern = re.compile(r'\b(\d+(?:\.\d+)?)\s*(kg|kilos?|pounds?|lbs?)\b', re.IGNORECASE)
                if not weight_pattern.search(text):
                    missing.append(rule.get("missing", f"Missing {field}"))
            elif field == "allergies":
                if not self._extract_allergies(text):
                    missing.append(rule.get("missing", f"Missing {field}"))
            elif field == "pain_assessment":
                if not self._extract_socrates_pain(text):
                    missing.append(rule.get("missing", f"Missing {field}"))
        
        return missing


# Singleton instance
_parser = None


def get_input_parser() -> InputParser:
    """Get or create InputParser singleton"""
    global _parser
    if _parser is None:
        _parser = InputParser()
    return _parser
