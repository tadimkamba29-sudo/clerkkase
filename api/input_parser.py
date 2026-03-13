"""
Input Parser for ClerKase  (Batch 4 — upgraded)
================================================

Public API — **unchanged** from Kimi original so index.py needs no edits:
  InputParser.parse(text, section_name)  → Dict
  InputParser._extract_socrates_pain(text)  → SocratesPain | None
  InputParser.check_completeness(text, section_name, template)  → List[str]
  get_input_parser()  → InputParser singleton

Internals replaced:
  All heavy lifting is now delegated to ClinicalInputParser from
  clinical_input_parser.py, which provides:
    • 15-category symptom synonym map (negation-aware)
    • Structured duration extraction (hours / days / weeks / months / years +
      relative phrases like "since yesterday", "a few days")
    • Full SOCRATES pain parser (site dict, character dict, radiation, NRS
      severity, exacerbating/relieving factors)
    • Age parser (years, years+months, months, weeks, days-old)
    • Sex inference from pronouns / keywords
    • Bulk-input detector (flags full clerking pastes)
    • Unknown-token detector (spots medical suffixes not in dictionary)
"""

import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

# ── Rich internal engine ─────────────────────────────────────────────────────
from clinical_input_parser import (
    ClinicalInputParser,
    SOCRATESPain as _SOCRATESPain,
    Symptom,
    Duration,
    parse_age,
    parse_sex,
    parse_socrates,
    extract_duration,
    extract_severity,
    detect_bulk_input,
)

# ── Internal engine singleton ────────────────────────────────────────────────
_ENGINE = ClinicalInputParser()


# ============================================================================
# SocratesPain  — backwards-compatible dataclass
# ============================================================================

class SocratesPain:
    """
    SOCRATES pain assessment.

    Matches the interface expected by index.py:
      .to_dict()   → Dict (includes is_complete key)
      all nine fields as optional attributes
    """

    def __init__(self, rich: Optional[_SOCRATESPain] = None):
        if rich is None:
            self.site = None
            self.onset = None
            self.character = None
            self.radiation = None
            self.associations: Optional[str] = None
            self.time_course = None
            self.exacerbating: Optional[str] = None
            self.relieving: Optional[str] = None
            self.severity = None
        else:
            self.site = rich.site
            self.onset = rich.onset
            self.character = rich.character
            self.radiation = rich.radiation

            # associations: List[str] in rich model → join to string
            self.associations = (
                ", ".join(rich.associations) if rich.associations else None
            )
            self.time_course = rich.time_course

            # exacerbating / relieving: List[str] → first item or None
            self.exacerbating = (
                rich.exacerbating_factors[0]
                if rich.exacerbating_factors
                else None
            )
            self.relieving = (
                rich.relieving_factors[0]
                if rich.relieving_factors
                else None
            )
            self.severity = rich.severity

    def is_complete(self) -> bool:
        return all([
            self.site, self.onset, self.character, self.radiation,
            self.associations, self.time_course, self.exacerbating,
            self.relieving, self.severity,
        ])

    def to_dict(self) -> Dict:
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
            "is_complete": self.is_complete(),
        }


# ============================================================================
# InputParser
# ============================================================================

class InputParser:
    """
    Parses clinical input text and extracts structured information.

    Delegates all NLP work to ClinicalInputParser (clinical_input_parser.py).
    """

    # ── Public API ─────────────────────────────────────────────────────────

    def parse(self, text: str, section_name: str = "general") -> Dict[str, Any]:
        """
        Parse clinical input text.

        Args:
            text:         The input text to parse.
            section_name: The section being parsed (used to gate which
                          sub-parsers run, matching Kimi's original behaviour).

        Returns:
            Dict with extracted entities and metadata.
        """
        parsed = _ENGINE.parse(text)
        rich_dict = _ENGINE.to_dict(parsed)

        result: Dict[str, Any] = {
            "original_text": text,
            "section": section_name,
            "parsed_at": datetime.utcnow().isoformat(),
            # ── Enriched fields from Claude's parser ──────────────────
            "is_bulk_input": rich_dict["is_bulk_input"],
            "detected_sections": rich_dict["detected_sections"],
            "unknown_tokens": rich_dict["unknown_tokens"],
            "age": rich_dict["age"],
            "sex": rich_dict["sex"],
            "duration_overall": rich_dict["duration_overall"],
            "negated_symptoms": rich_dict["negated_symptoms"],
        }

        # ── Section-specific parsing (mirrors Kimi's gating) ──────────
        if section_name in (
            "presenting_complaint",
            "history_presenting_complaint",
            "history_presenting_illness",
            "general",
        ):
            result["symptoms"] = self._symptoms_list(parsed.symptoms)
            result["duration"] = self._duration_dict(parsed.duration_overall)
            result["severity"] = self._severity_str(text)
            result["socrates_pain"] = (
                SocratesPain(parsed.pain).to_dict() if parsed.pain else None
            )

        elif section_name == "demographics":
            result["age"] = rich_dict["age"]
            result["sex"] = rich_dict["sex"]

        elif section_name == "drug_history":
            result["medications"] = self._extract_medications(text)
            result["allergies"] = self._extract_allergies(text)

        else:
            # For all other sections, still extract symptoms and duration
            result["symptoms"] = self._symptoms_list(parsed.symptoms)
            result["duration"] = self._duration_dict(parsed.duration_overall)

        # ── Entity list (always present) ───────────────────────────────
        result["entities"] = self._build_entities(parsed)

        return result

    def _extract_socrates_pain(self, text: str) -> Optional[SocratesPain]:
        """
        Extract SOCRATES pain assessment.  Called directly by index.py's
        /api/parse/socrates route.

        Returns SocratesPain (with .to_dict()) or None if no pain present.
        """
        rich = parse_socrates(text)
        if rich is None:
            return None
        return SocratesPain(rich)

    def check_completeness(
        self,
        text: str,
        section_name: str,
        template: Dict,
    ) -> List[str]:
        """
        Check if section input is complete based on template rules.

        Args:
            text:         The input text.
            section_name: The section name.
            template:     The rotation template dict.

        Returns:
            List of missing-field messages.
        """
        missing: List[str] = []

        # Find section in template
        section_template = None
        for section in template.get("sections", []):
            if section.get("name") == section_name:
                section_template = section
                break

        if not section_template:
            return missing

        parsed = _ENGINE.parse(text)
        rich_dict = _ENGINE.to_dict(parsed)

        for field, rule in section_template.get("clarification_rules", {}).items():
            message = rule.get("missing", f"Missing {field}")

            if field == "age":
                if not rich_dict["age"]:
                    missing.append(message)

            elif field == "duration":
                if not rich_dict["duration_overall"]:
                    missing.append(message)

            elif field == "weight":
                weight_re = re.compile(
                    r"\b(\d+(?:\.\d+)?)\s*(kg|kilos?|pounds?|lbs?)\b", re.I
                )
                if not weight_re.search(text):
                    missing.append(message)

            elif field == "allergies":
                if not self._extract_allergies(text):
                    missing.append(message)

            elif field == "pain_assessment":
                if not self._extract_socrates_pain(text):
                    missing.append(message)

            elif field == "symptoms":
                if not parsed.symptoms:
                    missing.append(message)

        return missing

    # ── Private helpers ────────────────────────────────────────────────────

    @staticmethod
    def _symptoms_list(symptoms: List[Symptom]) -> List[Dict]:
        """Convert Symptom objects to JSON-serialisable dicts."""
        result = []
        for s in symptoms:
            result.append({
                "symptom": s.canonical_name,
                "raw_text": s.raw_text,
                "negated": s.negated,
                "severity": s.severity,
                "duration": (
                    {"value": s.duration.value, "unit": s.duration.unit}
                    if s.duration else None
                ),
                "qualifiers": s.qualifiers,
            })
        return result

    @staticmethod
    def _duration_dict(duration: Optional[Duration]) -> Optional[Dict]:
        if not duration:
            return None
        return {
            "value": duration.value,
            "unit": duration.unit,
            "display": str(duration),
            "hours_equivalent": duration.to_hours(),
        }

    @staticmethod
    def _severity_str(text: str) -> Optional[str]:
        return extract_severity(text)

    @staticmethod
    def _extract_medications(text: str) -> List[Dict]:
        """
        Extract medication mentions from free text.
        Handles patterns like:
          "taking metformin 500mg", "on aspirin", "medications: ..."
        """
        meds: List[Dict] = []
        patterns = [
            re.compile(
                r"\b(?:taking|on|prescribed?|started?|given|administering?)\s+"
                r"([A-Za-z][\w\-]+(?:\s+\d+\s*(?:mg|g|mcg|ml))?)",
                re.I,
            ),
            re.compile(
                r"\bmedications?\s*:?\s*([A-Za-z][\w\s,\-]+?)(?:\.|;|$)",
                re.I,
            ),
        ]
        seen: set = set()
        for pattern in patterns:
            for m in pattern.finditer(text):
                raw = m.group(1).strip()
                if raw.lower() not in seen:
                    seen.add(raw.lower())
                    meds.append({
                        "medication": raw,
                        "position": (m.start(), m.end()),
                    })
        return meds

    @staticmethod
    def _extract_allergies(text: str) -> List[Dict]:
        """
        Extract allergy mentions from free text.
        Handles: "allergic to penicillin", "allergy: latex", "NKDA"
        """
        allergies: List[Dict] = []

        # "No known drug allergies / NKDA"
        if re.search(r"\b(?:nkda|no\s+known\s+(?:drug\s+)?allerg)", text, re.I):
            allergies.append({"allergen": "NKDA", "position": (0, 0)})
            return allergies

        patterns = [
            re.compile(
                r"\ballerg(?:y|ic|ies)\s+(?:to\s+)?([A-Za-z][\w\s\-]+?)"
                r"(?:\s*(?:—|–|-{1,2}|:|\()\s*[A-Za-z].*?)?(?:\.|,|;|$)",
                re.I,
            ),
            re.compile(
                r"\ballergic\s+to\s+([A-Za-z][\w\s\-]+?)"
                r"(?:\s*(?:—|–|-{1,2}|:|\()\s*[A-Za-z].*?)?(?:\.|,|;|$)",
                re.I,
            ),
        ]
        seen: set = set()
        for pattern in patterns:
            for m in pattern.finditer(text):
                raw = m.group(1).strip().rstrip(".,;")
                if raw.lower() not in seen:
                    seen.add(raw.lower())
                    allergies.append({
                        "allergen": raw,
                        "position": (m.start(), m.end()),
                    })
        return allergies

    def _build_entities(self, parsed) -> List[Dict]:
        """
        Build a flat entity list (all types) matching Kimi's original format.
        """
        entities: List[Dict] = []

        # Symptoms
        for s in parsed.symptoms:
            entities.append({
                "entity_type": "symptom",
                "value": s.canonical_name,
                "raw": s.raw_text,
                "negated": s.negated,
                "confidence": 0.85,
            })

        # Duration
        if parsed.duration_overall:
            entities.append({
                "entity_type": "duration",
                "value": str(parsed.duration_overall),
                "confidence": 0.9,
            })

        # Age
        if parsed.age:
            entities.append({
                "entity_type": "age",
                "value": parsed.age.get("display", ""),
                "total_months": parsed.age.get("total_months"),
                "confidence": 0.95,
            })

        # Sex
        if parsed.sex:
            entities.append({
                "entity_type": "sex",
                "value": parsed.sex,
                "confidence": 0.8,
            })

        # Pain SOCRATES (summary)
        if parsed.pain:
            entities.append({
                "entity_type": "pain",
                "value": "socrates_assessed",
                "site": parsed.pain.site,
                "character": parsed.pain.character,
                "severity": parsed.pain.severity,
                "confidence": 0.9,
            })

        return entities


# ============================================================================
# Singleton
# ============================================================================

_parser: Optional[InputParser] = None


def get_input_parser() -> InputParser:
    """Get or create the InputParser singleton."""
    global _parser
    if _parser is None:
        _parser = InputParser()
    return _parser
