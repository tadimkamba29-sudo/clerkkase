"""
Clarification Engine for ClerKase
Hybrid system combining rule-based and AI-powered clarification generation
"""

import os
import json
import re
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime

# Try to import Anthropic, but don't fail if not available
try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


@dataclass
class ClarificationResult:
    """Result from clarification engine"""
    questions: List[str]
    source: str  # "rules", "ai", or "hybrid"
    confidence: float
    reasoning: str


class RuleBasedClarifier:
    """
    Rule-based clarification using templates and pattern matching
    """
    
    def __init__(self):
        self._load_rules()
    
    def _load_rules(self):
        """Load clarification rules"""
        # These rules map section names to required fields and their questions
        self.section_rules = {
            "demographics": {
                "age": "What is the patient's age?",
                "weight": "What is the patient's current weight?",
                "gender": "What is the patient's gender?",
            },
            "presenting_complaint": {
                "complaint": "What is the main reason for the patient's presentation today?",
                "duration": "How long has this problem been present?",
            },
            "history_presenting_complaint": {
                "pain_assessment": "Has the patient reported any pain? If so, please assess using SOCRATES (Site, Onset, Character, Radiation, Associations, Time course, Exacerbating factors, Relieving factors, Severity).",
                "red_flags": "Are there any red flag symptoms that require urgent attention?",
            },
            "drug_history": {
                "allergies": "Does the patient have any known drug allergies? Please specify the allergen and reaction.",
                "current_medications": "What medications is the patient currently taking?",
            },
            "obstetric_history": {
                "gravida": "What is the gravidity (total number of pregnancies)?",
                "para": "What is the parity (number of births >24 weeks)?",
            },
            "birth_history": {
                "gestation": "What was the gestational age at birth?",
                "birth_weight": "What was the birth weight?",
            },
            "immunisation_history": {
                "up_to_date": "Are the patient's immunisations up to date?",
            },
            "triage_assessment": {
                "triage_category": "What is the triage category?",
            },
        }
        
        # Contradiction detection rules
        self.contradiction_rules = [
            {
                "name": "penicillin_allergy_with_penicillin",
                "description": "Patient has penicillin allergy but prescribed penicillin",
                "check": self._check_penicillin_contradiction,
                "message": "WARNING: Patient has documented penicillin allergy but has been prescribed a penicillin-containing medication."
            },
            {
                "name": "aspirin_allergy_with_aspirin",
                "description": "Patient has aspirin allergy but prescribed aspirin",
                "check": self._check_aspirin_contradiction,
                "message": "WARNING: Patient has documented aspirin/NSAID allergy but has been prescribed aspirin."
            },
            {
                "name": "timeline_inconsistency",
                "description": "Timeline inconsistency detected",
                "check": self._check_timeline_inconsistency,
                "message": "NOTE: There appears to be an inconsistency in the timeline. Please verify the dates."
            }
        ]
    
    def generate_clarifications(
        self,
        section_name: str,
        section_data: Dict[str, Any],
        template: Dict
    ) -> List[str]:
        """
        Generate clarifications based on rules
        
        Args:
            section_name: The section being checked
            section_data: Current section data
            template: The rotation template
            
        Returns:
            List of clarification questions
        """
        questions = []
        
        # Get rules for this section
        rules = self.section_rules.get(section_name, {})
        
        # Find section in template
        section_template = None
        for section in template.get("sections", []):
            if section["name"] == section_name:
                section_template = section
                break
        
        if not section_template:
            return questions
        
        # Check clarification rules from template
        template_rules = section_template.get("clarification_rules", {})
        
        for field, rule in template_rules.items():
            # Check if field is missing or empty
            field_value = section_data.get(field, "")
            if not field_value or field_value.strip() == "":
                questions.append(rule.get("missing", f"Please provide {field}"))
        
        # Check our built-in rules
        for field, question in rules.items():
            field_value = section_data.get(field, "")
            if not field_value or field_value.strip() == "":
                questions.append(question)
        
        return questions
    
    def detect_contradictions(
        self,
        all_sections: Dict[str, Dict[str, Any]]
    ) -> List[Dict]:
        """
        Detect contradictions across sections
        
        Args:
            all_sections: All section data
            
        Returns:
            List of detected contradictions
        """
        contradictions = []
        
        for rule in self.contradiction_rules:
            result = rule["check"](all_sections)
            if result:
                contradictions.append({
                    "type": rule["name"],
                    "message": rule["message"],
                    "severity": "high" if "WARNING" in rule["message"] else "medium"
                })
        
        return contradictions
    
    def _check_penicillin_contradiction(self, all_sections: Dict) -> bool:
        """Check for penicillin allergy with penicillin prescription"""
        drug_history = all_sections.get("drug_history", {})
        
        allergies_text = drug_history.get("allergies", "").lower()
        medications_text = drug_history.get("current_medications", "").lower()
        
        # Check for penicillin allergy
        has_penicillin_allergy = any(term in allergies_text for term in [
            "penicillin", "amoxicillin", "ampicillin", "flucloxacillin"
        ])
        
        # Check for penicillin prescription
        taking_penicillin = any(term in medications_text for term in [
            "penicillin", "amoxicillin", "ampicillin", "co-amoxiclav", "flucloxacillin"
        ])
        
        return has_penicillin_allergy and taking_penicillin
    
    def _check_aspirin_contradiction(self, all_sections: Dict) -> bool:
        """Check for aspirin allergy with aspirin prescription"""
        drug_history = all_sections.get("drug_history", {})
        
        allergies_text = drug_history.get("allergies", "").lower()
        medications_text = drug_history.get("current_medications", "").lower()
        
        # Check for aspirin/NSAID allergy
        has_aspirin_allergy = any(term in allergies_text for term in [
            "aspirin", "nsaid", "ibuprofen", "diclofenac", "naproxen"
        ])
        
        # Check for aspirin prescription
        taking_aspirin = any(term in medications_text for term in [
            "aspirin", "dispirin"
        ])
        
        return has_aspirin_allergy and taking_aspirin
    
    def _check_timeline_inconsistency(self, all_sections: Dict) -> bool:
        """Check for timeline inconsistencies"""
        # This is a simplified check - could be expanded
        hpc = all_sections.get("history_presenting_complaint", {})
        detailed_history = hpc.get("detailed_history", "")
        
        # Look for date patterns and check for inconsistencies
        date_patterns = [
            r'\b(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})\b',
            r'\b(\d{1,2})(?:st|nd|rd|th)?\s+(january|february|march|april|may|june|july|august|september|october|november|december)\b',
        ]
        
        dates_found = []
        for pattern in date_patterns:
            matches = re.findall(pattern, detailed_history.lower())
            dates_found.extend(matches)
        
        # If multiple dates found, flag for review
        # In a real implementation, we'd compare dates for logical consistency
        return len(dates_found) > 2


class AIClarifier:
    """
    AI-powered clarification using Claude API
    """
    
    def __init__(self):
        self.client = None
        self._init_client()
    
    def _init_client(self):
        """Initialize Claude client"""
        if ANTHROPIC_AVAILABLE:
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if api_key:
                self.client = anthropic.Anthropic(api_key=api_key)
    
    def is_available(self) -> bool:
        """Check if AI clarifier is available"""
        return self.client is not None
    
    def generate_clarifications(
        self,
        section_name: str,
        section_data: Dict[str, Any],
        template: Dict,
        all_sections: Optional[Dict[str, Dict[str, Any]]] = None
    ) -> ClarificationResult:
        """
        Generate AI-powered clarifications
        
        Args:
            section_name: The section being checked
            section_data: Current section data
            template: The rotation template
            all_sections: All sections data (for context)
            
        Returns:
            ClarificationResult with questions
        """
        if not self.is_available():
            return ClarificationResult(
                questions=[],
                source="ai",
                confidence=0.0,
                reasoning="AI not available - ANTHROPIC_API_KEY not set"
            )
        
        # Find section in template
        section_template = None
        for section in template.get("sections", []):
            if section["name"] == section_name:
                section_template = section
                break
        
        if not section_template:
            return ClarificationResult(
                questions=[],
                source="ai",
                confidence=0.0,
                reasoning="Section not found in template"
            )
        
        # Build prompt
        prompt = self._build_prompt(
            section_name,
            section_template,
            section_data,
            all_sections
        )
        
        try:
            # Call Claude API
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1000,
                temperature=0.3,
                system="You are a medical education assistant helping medical students complete clinical case documentation. Your task is to identify missing or incomplete information in clinical sections and generate specific, targeted clarification questions. Be concise and professional. Return only the questions, one per line.",
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            # Parse response
            content = response.content[0].text if response.content else ""
            questions = [q.strip() for q in content.split('\n') if q.strip() and not q.strip().startswith('#')]
            
            # Calculate confidence based on response quality
            confidence = 0.8 if questions else 0.3
            
            return ClarificationResult(
                questions=questions,
                source="ai",
                confidence=confidence,
                reasoning=f"Generated {len(questions)} questions using Claude AI"
            )
            
        except Exception as e:
            return ClarificationResult(
                questions=[],
                source="ai",
                confidence=0.0,
                reasoning=f"AI error: {str(e)}"
            )
    
    def _build_prompt(
        self,
        section_name: str,
        section_template: Dict,
        section_data: Dict[str, Any],
        all_sections: Optional[Dict[str, Dict[str, Any]]]
    ) -> str:
        """Build prompt for Claude API"""
        
        prompt = f"""Review the following clinical section and identify what important information is missing or needs clarification.

Section: {section_template.get('title', section_name)}

Current data:
"""
        
        # Add current data
        for field_name, value in section_data.items():
            prompt += f"- {field_name}: {value}\n"
        
        # Add context from other sections if available
        if all_sections:
            prompt += "\nContext from other sections:\n"
            for other_section, other_data in all_sections.items():
                if other_section != section_name and other_data:
                    # Add key fields from other sections
                    if other_section == "demographics":
                        prompt += f"- Demographics: Age {other_data.get('age', 'unknown')}, Gender {other_data.get('gender', 'unknown')}\n"
                    elif other_section == "presenting_complaint":
                        prompt += f"- Presenting Complaint: {other_data.get('complaint', 'unknown')}\n"
        
        # Add expected fields
        prompt += f"\nExpected fields for this section:\n"
        for field in section_template.get("fields", []):
            prompt += f"- {field.get('label', field['name'])}\n"
        
        prompt += """

Please generate 1-3 specific clarification questions that would help complete this section. Focus on:
1. Missing critical information
2. Ambiguous or unclear entries
3. Information that would be expected in a professional clerking

Return only the questions, one per line. Do not include numbering or bullet points."""
        
        return prompt


class ClarificationEngine:
    """
    Hybrid clarification engine combining rules and AI
    """
    
    def __init__(self, use_ai: bool = True):
        self.rule_clarifier = RuleBasedClarifier()
        self.ai_clarifier = AIClarifier() if use_ai else None
        self.use_ai = use_ai and self.ai_clarifier and self.ai_clarifier.is_available()
    
    def process_section(
        self,
        case_id: str,
        section_name: str,
        section_data: Dict[str, Any],
        template: Dict,
        all_sections: Optional[Dict[str, Dict[str, Any]]] = None
    ) -> ClarificationResult:
        """
        Process a section and generate clarifications
        
        Args:
            case_id: The case ID
            section_name: The section being processed
            section_data: Current section data
            template: The rotation template
            all_sections: All sections data
            
        Returns:
            ClarificationResult with questions
        """
        # First, get rule-based clarifications
        rule_questions = self.rule_clarifier.generate_clarifications(
            section_name, section_data, template
        )
        
        # Detect contradictions
        if all_sections:
            contradictions = self.rule_clarifier.detect_contradictions(all_sections)
            # Add contradiction warnings as questions
            for contradiction in contradictions:
                rule_questions.append(f"[{contradiction['severity'].upper()}] {contradiction['message']}")
        
        # If rule-based found issues, use those
        if rule_questions:
            return ClarificationResult(
                questions=rule_questions,
                source="rules",
                confidence=0.9,
                reasoning=f"Found {len(rule_questions)} issues using rule-based analysis"
            )
        
        # If no rule-based issues and AI is available, try AI
        if self.use_ai:
            ai_result = self.ai_clarifier.generate_clarifications(
                section_name, section_data, template, all_sections
            )
            
            if ai_result.questions:
                return ai_result
        
        # No clarifications needed
        return ClarificationResult(
            questions=[],
            source="hybrid",
            confidence=1.0,
            reasoning="No clarifications needed - section appears complete"
        )
    
    def detect_contradictions(
        self,
        all_sections: Dict[str, Dict[str, Any]]
    ) -> List[Dict]:
        """
        Detect contradictions across all sections
        
        Args:
            all_sections: All section data
            
        Returns:
            List of detected contradictions
        """
        return self.rule_clarifier.detect_contradictions(all_sections)
    
    def get_ai_status(self) -> Dict:
        """Get AI clarifier status"""
        return {
            "available": self.use_ai,
            "reason": "AI enabled" if self.use_ai else "AI not available - check ANTHROPIC_API_KEY"
        }


# Singleton instance
_engine = None


def get_clarification_engine(use_ai: bool = True) -> ClarificationEngine:
    """Get or create ClarificationEngine singleton"""
    global _engine
    if _engine is None:
        _engine = ClarificationEngine(use_ai=use_ai)
    return _engine
