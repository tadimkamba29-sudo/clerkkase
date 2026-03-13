"""
Clinical Input Parser - Enhanced Module
Converts messy clinical text into structured data.

Features:
- Synonym mapping (fever, vomiting, cough, etc.)
- Duration extraction
- SOCRATES pain parser
- Severity detection
- Bulk input detector
- Age parser
- Negation detection
"""

import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict


# ─────────────────────────────────────────────────────────────────────────────
# DATA MODELS
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Duration:
    value: int
    unit: str  # hours, days, weeks, months

    def to_hours(self) -> float:
        multipliers = {"hours": 1, "days": 24, "weeks": 168, "months": 720}
        return self.value * multipliers.get(self.unit, 0)

    def __str__(self):
        return f"{self.value} {self.unit}"


@dataclass
class Symptom:
    canonical_name: str
    raw_text: str
    duration: Optional[Duration] = None
    severity: Optional[str] = None
    negated: bool = False
    qualifiers: List[str] = field(default_factory=list)


@dataclass
class SOCRATESPain:
    """Structured pain assessment using SOCRATES framework."""
    site: Optional[str] = None
    onset: Optional[str] = None
    character: Optional[str] = None
    radiation: Optional[str] = None
    associations: List[str] = field(default_factory=list)
    time_course: Optional[str] = None
    exacerbating_factors: List[str] = field(default_factory=list)
    relieving_factors: List[str] = field(default_factory=list)
    severity: Optional[str] = None  # NRS 0-10 if mentioned
    duration: Optional[Duration] = None


@dataclass
class ParsedInput:
    raw_text: str
    is_bulk_input: bool
    detected_sections: List[str]
    symptoms: List[Symptom]
    pain: Optional[SOCRATESPain]
    age: Optional[Dict]
    sex: Optional[str]
    duration_overall: Optional[Duration]
    negated_symptoms: List[str]
    unknown_tokens: List[str]


# ─────────────────────────────────────────────────────────────────────────────
# SYNONYM MAPPER (1.1)
# ─────────────────────────────────────────────────────────────────────────────

SYMPTOM_SYNONYMS: Dict[str, List[str]] = {
    "fever": [
        "high temperature", "high temp", "pyrexia", "febrile", "hot",
        "temperature", "hyperthermia", r"\d+\.?\d*\s*°[CF]", r"\d+\.?\d*\s*degrees"
    ],
    "vomiting": [
        "vomits", "vomited", "vomit", "threw up", "throw up", "throwing up",
        "emesis", "sick", "toss", "retching", "retch", "nausea and vomiting"
    ],
    "cough": [
        "coughing", "barky cough", "wet cough", "dry cough", "productive cough",
        "non-productive cough", "whooping", "paroxysmal cough"
    ],
    "diarrhoea": [
        "diarrhea", "diarrhoea", "loose stools", "watery stools",
        "frequent stools", "loose motion", "runny poo", "runny stool"
    ],
    "rash": [
        "rash", "spots", "skin changes", "eruption", "redness", "urticaria",
        "hives", "maculopapular", "erythema", "vesicles", "blisters"
    ],
    "headache": [
        "headache", "head pain", "head ache", "migraine", "cephalalgia",
        "head hurts", "sore head", "head throbbing"
    ],
    "abdominal_pain": [
        "stomach pain", "belly pain", "tummy pain", "abdominal pain",
        "epigastric pain", "periumbilical pain", "right iliac fossa pain",
        "lower abdo pain", "stomach ache", "stomachache"
    ],
    "shortness_of_breath": [
        "breathlessness", "dyspnoea", "dyspnea", "short of breath",
        "difficulty breathing", "can't breathe", "hard to breathe",
        "respiratory distress", "sob", "laboured breathing"
    ],
    "seizure": [
        "fit", "fits", "convulsion", "convulsions", "jerking", "shaking",
        "twitching", "epilepsy", "febrile convulsion", "afebrile convulsion"
    ],
    "lethargy": [
        "lethargic", "tired", "fatigue", "fatigued", "weak", "weakness",
        "not active", "less active", "sleepy", "drowsy", "decreased activity"
    ],
    "poor_feeding": [
        "not feeding", "poor feed", "feeding poorly", "not eating",
        "refusing feeds", "refusing breast", "refusing bottle", "off feeds"
    ],
    "neck_stiffness": [
        "neck stiffness", "stiff neck", "neck rigidity", "nuchal rigidity", "can't flex neck"
    ],
    "ear_pain": [
        "earache", "ear ache", "otitis", "ear pain", "pulling at ear",
        "tugging ear"
    ],
    "sore_throat": [
        "throat pain", "throat ache", "odynophagia", "difficulty swallowing",
        "tonsillitis", "pharyngitis"
    ],
    "constipation": [
        "not passing stool", "no poo", "hard stools", "straining",
        "infrequent stools", "constipated"
    ],
    "jaundice": [
        "yellow skin", "yellow eyes", "yellowing", "icteric", "icterus"
    ],
}

# Compile regex-based synonyms (e.g., temperature values)
_COMPILED_SYNONYMS: Dict[str, List] = {}
for canonical, synonyms in SYMPTOM_SYNONYMS.items():
    compiled = []
    for s in synonyms:
        try:
            compiled.append(re.compile(s, re.IGNORECASE))
        except re.error:
            compiled.append(re.compile(re.escape(s), re.IGNORECASE))
    _COMPILED_SYNONYMS[canonical] = compiled


# ─────────────────────────────────────────────────────────────────────────────
# DURATION EXTRACTOR (1.2)
# ─────────────────────────────────────────────────────────────────────────────

DURATION_PATTERNS = [
    (re.compile(r"(\d+)\s*(?:hour|hours|hr|hrs|h)\b", re.I), "hours"),
    (re.compile(r"(\d+)\s*(?:day|days|d)\b", re.I), "days"),
    (re.compile(r"(\d+)\s*(?:week|weeks|wk|wks)\b", re.I), "weeks"),
    (re.compile(r"(\d+)\s*(?:month|months|mo|mos)\b", re.I), "months"),
    (re.compile(r"(\d+)\s*(?:year|years|yr|yrs)\b", re.I), "years"),
]

RELATIVE_DURATION_PATTERNS = [
    (re.compile(r"since\s+(?:this\s+)?morning", re.I), Duration(12, "hours")),
    (re.compile(r"since\s+(?:last\s+)?night", re.I), Duration(12, "hours")),
    (re.compile(r"since\s+yesterday", re.I), Duration(1, "days")),
    (re.compile(r"since\s+last\s+week", re.I), Duration(1, "weeks")),
    (re.compile(r"since\s+last\s+month", re.I), Duration(1, "months")),
    (re.compile(r"few\s+days", re.I), Duration(3, "days")),
    (re.compile(r"few\s+hours", re.I), Duration(4, "hours")),
    (re.compile(r"few\s+weeks", re.I), Duration(3, "weeks")),
]


def extract_duration(text: str) -> Optional[Duration]:
    """Extract duration from text. Returns first match found."""
    # Try relative patterns first
    for pattern, result in RELATIVE_DURATION_PATTERNS:
        if pattern.search(text):
            return result

    # Try numeric patterns
    for pattern, unit in DURATION_PATTERNS:
        match = pattern.search(text)
        if match:
            return Duration(value=int(match.group(1)), unit=unit)

    return None


# ─────────────────────────────────────────────────────────────────────────────
# SOCRATES PARSER (1.3)
# ─────────────────────────────────────────────────────────────────────────────

PAIN_SITES = {
    "epigastric": ["epigastric", "upper abdomen", "upper belly", "below ribs"],
    "periumbilical": ["periumbilical", "around navel", "around belly button", "umbilical"],
    "right_iliac_fossa": ["right iliac fossa", "rif", "right lower abdomen", "right lower belly"],
    "left_iliac_fossa": ["left iliac fossa", "lif", "left lower abdomen"],
    "chest": ["chest", "sternal", "precordial", "substernal"],
    "head": ["head", "frontal", "temporal", "occipital", "forehead"],
    "right_ear": ["right ear", "right side ear"],
    "left_ear": ["left ear", "left side ear"],
    "throat": ["throat", "pharynx", "tonsillar"],
    "flank": ["flank", "loin", "side"],
    "generalised": ["all over", "generalised", "generalized", "diffuse", "everywhere"],
}

PAIN_CHARACTERS = {
    "sharp": ["sharp", "stabbing", "knife-like", "piercing", "lancinating"],
    "dull": ["dull", "aching", "ache", "deep"],
    "burning": ["burning", "burning sensation", "heartburn"],
    "colicky": ["colicky", "cramp", "cramping", "spasmodic", "waves"],
    "throbbing": ["throbbing", "pulsating", "pounding", "pulsing"],
    "pressure": ["pressure", "tight", "tightness", "squeezing", "crushing"],
}

AGGRAVATING_FACTORS = [
    "eating", "food", "movement", "walking", "breathing", "coughing",
    "lying down", "bending", "palpation", "deep breath", "swallowing"
]

RELIEVING_FACTORS = [
    "rest", "lying down", "antacid", "food", "vomiting", "heat",
    "cold", "medication", "analgesic", "paracetamol", "ibuprofen"
]


def parse_socrates(text: str) -> Optional[SOCRATESPain]:
    """Parse SOCRATES elements from pain-related text."""
    text_lower = text.lower()

    # Only proceed if pain-related
    pain_triggers = ["pain", "ache", "aching", "sore", "hurt", "hurts", "discomfort"]
    if not any(t in text_lower for t in pain_triggers):
        return None

    pain = SOCRATESPain()

    # Site
    for site, keywords in PAIN_SITES.items():
        if any(k in text_lower for k in keywords):
            pain.site = site
            break

    # Character
    for char, keywords in PAIN_CHARACTERS.items():
        if any(k in text_lower for k in keywords):
            pain.character = char
            break

    # Duration
    pain.duration = extract_duration(text)

    # Radiation
    radiation_match = re.search(
        r"(?:radiat|spread|go(?:es)? to|shoot)\w*\s+(?:to\s+)?(\w+(?:\s+\w+)?)",
        text_lower
    )
    if radiation_match:
        pain.radiation = radiation_match.group(1)

    # Exacerbating factors
    aggravate_match = re.search(
        r"(?:worse|worsened?|aggravated?|exacerbated?)\s+(?:by|with|on|when)\s+([^,.]+)",
        text_lower
    )
    if aggravate_match:
        pain.exacerbating_factors = [aggravate_match.group(1).strip()]
    else:
        pain.exacerbating_factors = [f for f in AGGRAVATING_FACTORS if f in text_lower]

    # Relieving factors
    relieve_match = re.search(
        r"(?:better|relieved?|improve[sd]*)\s+(?:by|with|on|when)\s+([^,.]+)",
        text_lower
    )
    if relieve_match:
        pain.relieving_factors = [relieve_match.group(1).strip()]
    else:
        pain.relieving_factors = [f for f in RELIEVING_FACTORS if f in text_lower]

    # Severity (NRS)
    nrs_match = re.search(r"(\d{1,2})\s*/\s*10", text_lower)
    if nrs_match:
        pain.severity = f"{nrs_match.group(1)}/10"

    # Time course (constant vs intermittent)
    if any(w in text_lower for w in ["constant", "continuous", "persistent"]):
        pain.time_course = "constant"
    elif any(w in text_lower for w in ["intermittent", "comes and goes", "episodic", "on and off"]):
        pain.time_course = "intermittent"

    return pain


# ─────────────────────────────────────────────────────────────────────────────
# NEGATION DETECTOR
# ─────────────────────────────────────────────────────────────────────────────

NEGATION_TRIGGERS = [
    r"\bno\b", r"\bnot\b", r"\bnever\b", r"\bdenies?\b", r"\bwithout\b",
    r"\babsence of\b", r"\bno history of\b", r"\bnegative for\b"
]

NEGATION_WINDOW = 5  # words after negation trigger


def detect_negation(text: str, symptom_position: int) -> bool:
    """Check if a symptom occurrence is negated."""
    words = text[:symptom_position].split()
    window = words[-NEGATION_WINDOW:]
    window_text = " ".join(window)
    return any(re.search(pattern, window_text, re.I) for pattern in NEGATION_TRIGGERS)


# ─────────────────────────────────────────────────────────────────────────────
# BULK INPUT DETECTOR (1.4)
# ─────────────────────────────────────────────────────────────────────────────

SECTION_HEADERS = [
    r"(?:chief\s+complaints?|presenting\s+complaints?)",
    r"(?:history\s+of\s+presenting\s+illness|hpi|presenting\s+history)",
    r"(?:past\s+(?:medical\s+)?history|pmh)",
    r"(?:drug\s+history|medications?|current\s+medications?)",
    r"(?:family\s+history|fh)",
    r"(?:social\s+history|sh)",
    r"(?:review\s+of\s+systems?|ros|systematic\s+enquiry)",
    r"(?:immunization|vaccination|immunisation)\s+history",
    r"(?:birth|perinatal|neonatal)\s+history",
    r"(?:developmental\s+history)",
    r"(?:physical\s+examination|examination\s+findings?)",
    r"(?:vital\s+signs?|vitals)",
    r"(?:investigations?|results?|labs?)",
]

BULK_INDICATORS = [
    len,  # checked separately: word count > 80
] + [re.compile(pattern, re.I) for pattern in SECTION_HEADERS]


def detect_bulk_input(text: str) -> Tuple[bool, List[str]]:
    """
    Detect if input is a bulk paste (entire clerking) vs single section.
    Returns (is_bulk, detected_sections).
    """
    text_lower = text.lower()
    found_sections = []

    for pattern in BULK_INDICATORS[1:]:  # skip the `len` placeholder
        match = pattern.search(text_lower)
        if match:
            found_sections.append(match.group(0))

    word_count = len(text.split())
    is_bulk = word_count > 80 or len(found_sections) >= 2

    return is_bulk, found_sections


# ─────────────────────────────────────────────────────────────────────────────
# AGE PARSER
# ─────────────────────────────────────────────────────────────────────────────

def parse_age(text: str) -> Optional[Dict]:
    """Extract age from text and normalize to months."""
    text_lower = text.lower()

    # Years + months (e.g., "2 years 3 months", "2y3m")
    ym_match = re.search(
        r"(\d+)\s*[-\s]?(?:year|years|yr|yrs|y)\s*[-\s]?(?:old\s+)?(?:and\s+)?(\d+)\s*(?:month|months|mo|m)",
        text_lower
    )
    if ym_match:
        years, months = int(ym_match.group(1)), int(ym_match.group(2))
        total_months = years * 12 + months
        return {"years": years, "months": months, "total_months": total_months,
                "display": f"{years}y {months}m"}

    # Years only (handles "5-year-old", "5 year old", "5y")
    y_match = re.search(r"(\d+)\s*[-\s]?(?:year|years|yr|yrs|y)(?:\s*-?\s*old)?", text_lower)
    if y_match:
        years = int(y_match.group(1))
        return {"years": years, "months": 0, "total_months": years * 12,
                "display": f"{years}y"}

    # Months only
    mo_match = re.search(r"(\d+)\s*(?:month|months|mo|mos)\b", text_lower)
    if mo_match:
        months = int(mo_match.group(1))
        return {"years": 0, "months": months, "total_months": months,
                "display": f"{months} months"}

    # Weeks (neonate)
    wk_match = re.search(r"(\d+)\s*(?:week|weeks|wk|wks)\b", text_lower)
    if wk_match:
        weeks = int(wk_match.group(1))
        return {"years": 0, "months": 0, "weeks": weeks,
                "total_months": round(weeks / 4.3, 1),
                "display": f"{weeks} weeks"}

    # Days (neonate)
    d_match = re.search(r"(\d+)\s*(?:day|days|d)\s*old", text_lower)
    if d_match:
        days = int(d_match.group(1))
        return {"years": 0, "months": 0, "days": days,
                "total_months": round(days / 30, 2),
                "display": f"{days} days old"}

    return None


# ─────────────────────────────────────────────────────────────────────────────
# SEX PARSER
# ─────────────────────────────────────────────────────────────────────────────

def parse_sex(text: str) -> Optional[str]:
    text_lower = text.lower()
    if re.search(r"\b(?:boy|male|m|his|him|he)\b", text_lower):
        return "male"
    if re.search(r"\b(?:girl|female|f|her|she)\b", text_lower):
        return "female"
    return None


# ─────────────────────────────────────────────────────────────────────────────
# SEVERITY EXTRACTOR
# ─────────────────────────────────────────────────────────────────────────────

def extract_severity(text: str) -> Optional[str]:
    text_lower = text.lower()
    if any(w in text_lower for w in ["severe", "bad", "terrible", "worst", "very high"]):
        return "severe"
    elif any(w in text_lower for w in ["mild", "slight", "little", "low-grade"]):
        return "mild"
    elif any(w in text_lower for w in ["moderate", "moderate-grade"]):
        return "moderate"
    return None


# ─────────────────────────────────────────────────────────────────────────────
# MAIN PARSER CLASS
# ─────────────────────────────────────────────────────────────────────────────

class ClinicalInputParser:
    """
    Main entry point. Converts messy clinical text into structured ParsedInput.
    """

    def parse(self, text: str) -> ParsedInput:
        is_bulk, sections = detect_bulk_input(text)

        symptoms = self._extract_all_symptoms(text)
        pain = parse_socrates(text)
        age = parse_age(text)
        sex = parse_sex(text)
        duration = extract_duration(text)
        negated = [s.canonical_name for s in symptoms if s.negated]

        return ParsedInput(
            raw_text=text,
            is_bulk_input=is_bulk,
            detected_sections=sections,
            symptoms=symptoms,
            pain=pain,
            age=age,
            sex=sex,
            duration_overall=duration,
            negated_symptoms=negated,
            unknown_tokens=self._find_unknown_tokens(text, symptoms),
        )

    def _extract_all_symptoms(self, text: str) -> List[Symptom]:
        symptoms = []
        for canonical, compiled_patterns in _COMPILED_SYNONYMS.items():
            for pattern in compiled_patterns:
                match = pattern.search(text)
                if match:
                    negated = detect_negation(text, match.start())
                    duration = extract_duration(text)
                    severity = extract_severity(text)
                    symptoms.append(Symptom(
                        canonical_name=canonical,
                        raw_text=match.group(0),
                        duration=duration,
                        severity=severity,
                        negated=negated,
                    ))
                    break  # one match per canonical term
        return symptoms

    def _find_unknown_tokens(self, text: str, known_symptoms: List[Symptom]) -> List[str]:
        """Identify potential clinical terms not in our dictionary."""
        medical_suffix = re.compile(
            r"\b\w+(?:itis|osis|emia|uria|pathy|algia|rrhoea|rrhea|megaly|plasty)\b",
            re.I
        )
        known_raw = {s.raw_text.lower() for s in known_symptoms}
        unknowns = []
        for match in medical_suffix.finditer(text):
            if match.group(0).lower() not in known_raw:
                unknowns.append(match.group(0))
        return list(set(unknowns))

    def to_dict(self, parsed: ParsedInput) -> Dict:
        """Convert ParsedInput to JSON-serializable dict."""
        result = {
            "is_bulk_input": parsed.is_bulk_input,
            "detected_sections": parsed.detected_sections,
            "symptoms": [
                {
                    "name": s.canonical_name,
                    "raw": s.raw_text,
                    "negated": s.negated,
                    "severity": s.severity,
                    "duration": asdict(s.duration) if s.duration else None,
                }
                for s in parsed.symptoms
            ],
            "negated_symptoms": parsed.negated_symptoms,
            "pain": asdict(parsed.pain) if parsed.pain else None,
            "age": parsed.age,
            "sex": parsed.sex,
            "duration_overall": asdict(parsed.duration_overall) if parsed.duration_overall else None,
            "unknown_tokens": parsed.unknown_tokens,
        }
        return result


# ─────────────────────────────────────────────────────────────────────────────
# EXAMPLE USAGE
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import json

    parser = ClinicalInputParser()

    test_cases = [
        "5-year-old boy with high temp for 3 days and vomiting",
        "Sharp epigastric pain 7/10, worse after eating, for 2 hours. No radiation.",
        "18-month-old girl with fever, cough and runny nose since last week. No rash.",
        """
        Chief Complaints: Fever and cough for 5 days
        HPI: A 2-year-old male presented with high temperature for 5 days.
             Mother reports poor feeding and lethargy. No rash or neck stiffness.
        Past Medical History: Nil significant
        """,
    ]

    for i, text in enumerate(test_cases, 1):
        result = parser.parse(text)
        print(f"\n{'='*60}")
        print(f"TEST {i}: {text[:60].strip()}...")
        print(f"{'='*60}")
        print(json.dumps(parser.to_dict(result), indent=2))
