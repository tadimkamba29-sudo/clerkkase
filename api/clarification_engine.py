"""
Clarification Engine for ClerKase
===================================
Hybrid system: rule-based first, AI fallback when rules pass clean.

Public API (unchanged from Kimi original — index.py needs no edits)
--------------------------------------------------------------------
  engine.process_section(case_id, section_name, section_data,
                          template, all_sections=None)
      → ClarificationResult

  engine.detect_contradictions(all_sections)
      → List[Dict]  (each dict has type, message, severity)

  engine.get_ai_status()
      → Dict

Improvements over previous version
------------------------------------
1. Section rules expanded from 8 fields to full coverage of all 6 rotations
2. Rotation-specific rules (Surgery, Paeds, Obs/Gyn, Psychiatry, Emergency)
3. Age/sex-adaptive questioning (never asks menstrual Hx to males, etc.)
4. SOCRATES completeness check — detects missing elements individually
5. Drug-class allergy checking (amoxicillin → flags penicillin allergy class)
6. Physiologically impossible vital-sign validation with proper ranges
7. Paediatric immunisation-vs-age checking
8. Proper timeline contradiction logic — replaces the date-count heuristic
9. Pregnancy/obstetric contradiction checks
"""

import os
import json
import re
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class ClarificationResult:
    """Returned by process_section()."""
    questions: List[str]
    source: str          # "rules" | "ai" | "hybrid" | "none"
    confidence: float
    reasoning: str


# ============================================================================
# DRUG CLASS MAP
# Penicillin allergy → flag amoxicillin, ampicillin, co-amoxiclav, etc.
# ============================================================================

DRUG_CLASS_MAP: Dict[str, List[str]] = {
    # Penicillins
    "penicillin":    ["amoxicillin", "ampicillin", "flucloxacillin",
                      "co-amoxiclav", "piperacillin", "tazobactam",
                      "benzylpenicillin", "phenoxymethylpenicillin"],
    "amoxicillin":   ["amoxicillin", "co-amoxiclav"],
    # Cephalosporins (partial cross-react with penicillin)
    "cephalosporin": ["cefalexin", "cefuroxime", "ceftriaxone",
                      "cefotaxime", "ceftazidime", "cefadroxil"],
    # Sulfonamides
    "sulfonamide":   ["trimethoprim-sulfamethoxazole", "co-trimoxazole",
                      "sulfamethoxazole", "sulfadiazine"],
    # NSAIDs
    "nsaid":         ["ibuprofen", "diclofenac", "naproxen",
                      "indomethacin", "ketorolac", "mefenamic acid"],
    "aspirin":       ["aspirin", "acetylsalicylic acid", "dispirin"],
    # Opioids
    "morphine":      ["morphine", "codeine", "tramadol"],
    # Contrast
    "contrast":      ["iodine contrast", "contrast media"],
    # Latex
    "latex":         ["latex", "rubber"],
}


def _normalize_drug(name: str) -> str:
    return name.lower().strip()


def _drugs_conflict(allergen: str, prescribed: str) -> bool:
    """
    Return True if *prescribed* belongs to the same class as *allergen*
    or is the same drug.
    """
    a = _normalize_drug(allergen)
    p = _normalize_drug(prescribed)

    if a == p:
        return True

    # Check if allergen is a class key
    related = DRUG_CLASS_MAP.get(a, [])
    if p in related:
        return True

    # Check if allergen is a member of any class that also contains prescribed
    for class_members in DRUG_CLASS_MAP.values():
        if a in class_members and p in class_members:
            return True

    return False


# ============================================================================
# RULE-BASED CLARIFIER
# ============================================================================

class RuleBasedClarifier:
    """
    Generates clarification questions from static rules and template metadata.

    Strategy
    --------
    1. Check template clarification_rules for the section
    2. Apply built-in section rules (demographics, HPI, drug Hx, etc.)
    3. Apply rotation-specific extra rules
    4. Apply age/sex filters to skip irrelevant questions
    5. Run cross-section contradiction checks
    """

    # ------------------------------------------------------------------
    # SECTION RULES
    # Missing field → question text.  Keys match JSON template field names.
    # ------------------------------------------------------------------
    SECTION_RULES: Dict[str, Dict[str, str]] = {
        # ── Demographics ──────────────────────────────────────────────
        "demographics": {
            "age":    "What is the patient's age?",
            "weight": "What is the patient's weight (kg)?",
            "gender": "What is the patient's gender? (Male / Female / Other)",
            "nhs_number": "What is the NHS / hospital number?",
        },
        # ── Presenting complaint ──────────────────────────────────────
        "presenting_complaint": {
            "complaint": "What is the main reason for the patient's presentation today?",
            "duration":  "How long has this problem been present?",
        },
        # ── History of presenting complaint ───────────────────────────
        "history_presenting_complaint": {
            "detailed_history": (
                "Please provide the full history of the presenting complaint, "
                "including onset, duration, character, progression, and associated symptoms."
            ),
            "pain_assessment": (
                "Has the patient reported pain? If so, complete a SOCRATES assessment: "
                "Site, Onset, Character, Radiation, Associations, Time course, "
                "Exacerbating / Relieving factors, and Severity (0–10)."
            ),
            "red_flags": (
                "Are there any red flag symptoms present? "
                "(e.g. weight loss, haemoptysis, melaena, new neurological symptoms)"
            ),
        },
        # ── Drug / allergy history ────────────────────────────────────
        "drug_history": {
            "allergies":          (
                "Does the patient have any known drug allergies? "
                "If yes, specify the allergen and the reaction type."
            ),
            "current_medications": "What medications is the patient currently taking?",
        },
        # ── Past medical / surgical history ──────────────────────────
        "past_medical_history": {
            "medical_conditions":  "Any significant past medical conditions?",
            "previous_admissions": "Any previous hospital admissions? If yes, details?",
        },
        "past_surgical_history": {
            "previous_operations": "Any previous operations? If yes, what and when?",
            "anaesthetic_problems": "Any problems with previous anaesthetics?",
        },
        # ── Family history ────────────────────────────────────────────
        "family_history": {
            "family_conditions": (
                "Any relevant family history? "
                "(Cardiovascular disease, diabetes, cancer, genetic conditions)"
            ),
        },
        # ── Social history ────────────────────────────────────────────
        "social_history": {
            "smoking":   "Does the patient smoke? Pack-year history?",
            "alcohol":   "Does the patient drink alcohol? Units per week?",
            "occupation": "What is the patient's occupation?",
            "living_situation": "Who does the patient live with and what is their housing situation?",
        },
        # ── Systems review ────────────────────────────────────────────
        "systems_review": {
            "cardiovascular": "Cardiovascular review: chest pain, palpitations, dyspnoea, oedema?",
            "respiratory":    "Respiratory review: cough, sputum, haemoptysis, wheeze?",
            "gastrointestinal": "GI review: nausea, vomiting, change in bowel habit, rectal bleeding?",
            "genitourinary":  "GU review: dysuria, haematuria, frequency, discharge?",
            "neurological":   "Neurological review: headache, dizziness, visual changes, weakness?",
        },
        # ── Physical examination ──────────────────────────────────────
        "physical_examination": {
            "vital_signs":          "Please document all vital signs: temperature, pulse, BP, RR, SpO₂.",
            "general_examination":  "Describe the general examination (consciousness, distress, nutritional status).",
            "systemic_examination": "What were the findings on systemic examination?",
        },
        # ── Obstetric history ─────────────────────────────────────────
        "obstetric_history": {
            "gravida":    "What is the gravidity (total number of pregnancies)?",
            "para":       "What is the parity (deliveries ≥ 24 weeks)?",
            "lmp":        "When was the first day of the last menstrual period (LMP)?",
        },
        # ── Birth / neonatal history (Paediatrics) ────────────────────
        "birth_history": {
            "gestation":    "What was the gestational age at birth (weeks)?",
            "birth_weight": "What was the birth weight (grams or kg)?",
            "delivery_mode": "Was the delivery normal vaginal / assisted / caesarean section?",
            "neonatal_complications": "Were there any neonatal complications (NICU, jaundice, resuscitation)?",
        },
        # ── Developmental history (Paediatrics) ───────────────────────
        "developmental_history": {
            "gross_motor":    "Gross motor milestones: sitting, standing, walking?",
            "fine_motor":     "Fine motor milestones: pincer grip, drawing?",
            "speech_language": "Speech and language: first words, sentences?",
            "social":         "Social milestones: smiling, eye contact, play?",
        },
        # ── Immunisation history (Paediatrics) ───────────────────────
        "immunisation_history": {
            "up_to_date":        "Are the patient's immunisations up to date for age?",
            "vaccines_received": "Which vaccines have been given and at what ages?",
        },
        # ── Triage (Emergency) ────────────────────────────────────────
        "triage_assessment": {
            "triage_category":  "What is the triage category (1–5)?",
            "triage_complaint": "What was the triage presenting complaint?",
            "arrival_mode":     "How did the patient arrive? (Walk-in / Ambulance / Transferred)",
        },
        # ── Mental state examination (Psychiatry) ────────────────────
        "mental_state_examination": {
            "appearance_behaviour": "Describe appearance and behaviour.",
            "speech":               "Describe speech (rate, rhythm, volume, content).",
            "mood_affect":          "What is the patient's mood and affect?",
            "thought":              "Describe thought form and content (including suicidal ideation).",
            "perception":           "Any perceptual disturbances (hallucinations, illusions)?",
            "cognition":            "Cognitive assessment: orientation, memory, attention.",
            "insight_judgement":    "Insight and judgement?",
        },
        # ── Psychiatric history ───────────────────────────────────────
        "psychiatric_history": {
            "previous_episodes":    "Any previous psychiatric episodes or admissions?",
            "current_treatment":    "Any current psychiatric medications or community support?",
            "risk_assessment":      (
                "Risk assessment: suicidal ideation, self-harm history, "
                "risk to others, safeguarding concerns?"
            ),
        },
        # ── Surgical pre-op (Surgery rotation) ───────────────────────
        "surgical_history": {
            "indication":          "What is the indication for surgery?",
            "consent":             "Has informed consent been obtained and documented?",
            "fasting_status":      "What is the patient's fasting status (last food / fluid)?",
        },
    }

    # ------------------------------------------------------------------
    # ROTATION-SPECIFIC EXTRA RULES
    # Triggered when a keyword is found in the HPI text.
    # ------------------------------------------------------------------
    ROTATION_RULES: Dict[str, List[Dict]] = {
        "surgery": [
            {
                "trigger_keywords": ["pain", "abdomen", "abdominal", "belly"],
                "if_missing_keyword": ["bowel", "stool", "flatus", "opening bowels"],
                "question": "When was the last bowel movement? Is the patient passing flatus?",
                "reason": "Critical for acute abdomen assessment — obstruction vs non-obstruction.",
            },
            {
                "trigger_keywords": ["pain", "abdomen", "abdominal", "belly"],
                "if_missing_keyword": ["vomit", "vomiting", "nausea"],
                "question": "Any nausea or vomiting? If yes — frequency, content (food/bile/blood), projectile?",
                "reason": "Important for surgical differential (obstruction, peritonitis).",
            },
            {
                "trigger_keywords": ["operation", "surgery", "procedure"],
                "if_missing_keyword": ["fasting", "nil by mouth", "nbm", "last ate"],
                "question": "What is the patient's current fasting status (last food and last fluid)?",
                "reason": "Essential pre-operative safety check.",
            },
        ],
        "paediatrics": [
            {
                "trigger_keywords": [],   # always apply for age < 5
                "age_max": 5,
                "if_missing_keyword": ["feed", "feeding", "breast", "bottle", "appetite"],
                "question": "How has this illness affected feeding? (Breastfeeding / bottle / solids — volume and frequency change)",
                "reason": "Feeding assessment is critical in young children.",
            },
            {
                "trigger_keywords": ["rash", "fever", "temperature"],
                "if_missing_keyword": ["contact", "exposure", "school", "sibling"],
                "question": "Any sick contacts? (Family, school, close community — similar illness or known infections such as measles, chickenpox, TB)",
                "reason": "Infectious disease contact history.",
            },
            {
                "trigger_keywords": ["cough", "wheeze", "breathless", "breathing"],
                "if_missing_keyword": ["inhaler", "nebuliser", "salbutamol"],
                "question": "Does the child use any inhalers or nebulisers? Have they been used today?",
                "reason": "Asthma management assessment.",
            },
        ],
        "obstetrics_gynaecology": [
            {
                "trigger_keywords": [],   # always apply to female patients
                "sex_filter": "female",
                "if_missing_keyword": ["lmp", "last menstrual period", "period"],
                "question": "What was the first day of the last menstrual period (LMP)?",
                "reason": "Essential for pregnancy assessment and gynaecological diagnosis.",
            },
            {
                "trigger_keywords": [],
                "sex_filter": "female",
                "if_missing_keyword": ["pregnant", "pregnancy", "gravida", "gestation"],
                "question": "Is there any possibility of pregnancy? What is the gravidity and parity?",
                "reason": "Critical for all female patients of reproductive age.",
            },
            {
                "trigger_keywords": ["bleed", "bleeding", "blood", "pv"],
                "if_missing_keyword": ["amount", "clots", "pad", "tampon"],
                "question": "Quantify the bleeding: number of pads/tampons per day, presence of clots, colour?",
                "reason": "Guides urgency and differential (APH, miscarriage, ectopic).",
            },
        ],
        "internal_medicine": [
            {
                "trigger_keywords": ["chest pain", "chest tightness", "angina"],
                "if_missing_keyword": ["radiation", "radiates", "jaw", "arm", "shoulder"],
                "question": "Does the chest pain radiate? (Jaw, left arm, shoulder, back?)",
                "reason": "Radiation pattern is key for distinguishing ACS from other causes.",
            },
            {
                "trigger_keywords": ["breathless", "dyspnoea", "short of breath"],
                "if_missing_keyword": ["orthopnoea", "pnd", "paroxysmal", "pillow"],
                "question": "Any orthopnoea (breathlessness lying flat) or paroxysmal nocturnal dyspnoea? How many pillows does the patient sleep with?",
                "reason": "Orthopnoea / PND suggest cardiac failure.",
            },
            {
                "trigger_keywords": ["diabetes", "diabetic", "glucose", "sugar"],
                "if_missing_keyword": ["hba1c", "glucose", "metformin", "insulin", "control"],
                "question": "What is the current blood glucose control — last HbA1c, current medications, and any recent hypoglycaemic episodes?",
                "reason": "Diabetic management assessment.",
            },
        ],
        "emergency_medicine": [
            {
                "trigger_keywords": ["trauma", "injury", "accident", "fall", "rta"],
                "if_missing_keyword": ["mechanism", "speed", "height", "force"],
                "question": "Describe the mechanism of injury: speed involved, height of fall, protective equipment worn?",
                "reason": "Mechanism determines likely injury pattern (ATLS principles).",
            },
            {
                "trigger_keywords": ["overdose", "od", "tablets", "ingestion"],
                "if_missing_keyword": ["what", "how many", "when", "tablets", "amount"],
                "question": "What substance was taken, how much, and at what time? Any co-ingestion of alcohol or other drugs?",
                "reason": "Overdose management depends on substance, amount, and timing.",
            },
            {
                "trigger_keywords": ["unconscious", "gcs", "unresponsive", "collapse"],
                "if_missing_keyword": ["gcs", "glasgow", "verbal", "motor", "eye"],
                "question": "Document the full GCS score (Eye / Verbal / Motor) and any change over time.",
                "reason": "GCS trend guides urgency and management.",
            },
        ],
        "psychiatry": [
            {
                "trigger_keywords": [],   # always check risk in psychiatry
                "if_missing_keyword": ["suicid", "self-harm", "harm", "risk"],
                "question": "Risk assessment: Any suicidal ideation (passive or active), plan, intent, or recent acts of self-harm? Any risk to others?",
                "reason": "Mandatory risk assessment in all psychiatric presentations.",
            },
            {
                "trigger_keywords": ["depress", "low mood", "sad", "hopeless"],
                "if_missing_keyword": ["sleep", "appetite", "concentration", "anhedonia"],
                "question": "Biological symptoms of depression: changes in sleep, appetite, concentration, energy, and ability to experience pleasure (anhedonia)?",
                "reason": "Biological symptom count informs severity and treatment decisions.",
            },
            {
                "trigger_keywords": ["psychosis", "hallucin", "voices", "paranoia", "delusion"],
                "if_missing_keyword": ["command", "duration", "insight"],
                "question": "Are the hallucinations command in nature? Duration and onset? Does the patient have insight into their experiences?",
                "reason": "Command hallucinations are a high-risk indicator.",
            },
        ],
    }

    # ------------------------------------------------------------------
    # SOCRATES element keywords
    # ------------------------------------------------------------------
    SOCRATES_KEYWORDS = {
        "site":        ["site", "where", "location", "localised", "localized"],
        "onset":       ["onset", "started", "began", "sudden", "gradual", "when did"],
        "character":   ["character", "nature", "type", "sharp", "dull", "burning",
                        "stabbing", "aching", "throbbing", "cramping"],
        "radiation":   ["radiat", "spread", "goes to", "travel"],
        "associations": ["associated", "accompan", "other symptoms", "nausea",
                         "vomiting", "fever", "sweating"],
        "time_course": ["constant", "intermittent", "comes and goes", "time course",
                        "frequency", "how often", "continuous"],
        "exacerbating": ["worse", "exacerbat", "aggravat", "brings on", "makes it worse"],
        "relieving":   ["better", "reliev", "eases", "settles", "improves"],
        "severity":    ["/10", "out of 10", "mild", "moderate", "severe",
                        "score", "rate the pain"],
    }

    def generate_clarifications(
        self,
        section_name: str,
        section_data: Dict[str, Any],
        template: Dict,
        all_sections: Optional[Dict] = None,
        patient_age: Optional[int] = None,
        patient_sex: Optional[str] = None,
        rotation: Optional[str] = None,
    ) -> List[str]:
        """
        Return a list of clarification question strings for this section.
        """
        questions: List[str] = []
        seen: set = set()

        def add(q: str):
            key = q.strip().lower()
            if key not in seen:
                seen.add(key)
                questions.append(q.strip())

        # 1. Template clarification_rules (highest priority — from JSON)
        section_tmpl = self._find_section_template(template, section_name)
        if section_tmpl:
            for field, rule in section_tmpl.get("clarification_rules", {}).items():
                val = section_data.get(field, "")
                if not val or (isinstance(val, str) and not val.strip()):
                    msg = rule.get("missing")
                    if msg:
                        add(msg)

        # 2. Built-in section rules
        for field, question in self.SECTION_RULES.get(section_name, {}).items():
            val = section_data.get(field, "")
            if not val or (isinstance(val, str) and not val.strip()):
                # Skip sex-specific fields
                if self._skip_for_sex(field, patient_sex):
                    continue
                # Skip age-inappropriate fields
                if self._skip_for_age(field, patient_age):
                    continue
                add(question)

        # 3. SOCRATES check — only for sections that contain pain narrative
        if section_name in (
            "history_presenting_complaint",
            "history_presenting_illness",
            "presenting_complaint",
        ):
            hpi_text = (
                section_data.get("detailed_history")
                or section_data.get("pain_assessment")
                or section_data.get("content")
                or ""
            )
            if self._text_contains_pain(hpi_text):
                for q in self._check_socrates(hpi_text):
                    add(q)

        # 4. Rotation-specific rules
        if rotation:
            rotation_key = rotation.lower().replace(" ", "_").replace("&", "").replace("__", "_")
            for rule in self.ROTATION_RULES.get(rotation_key, []):
                # Sex filter
                if "sex_filter" in rule:
                    if not patient_sex or patient_sex.lower() != rule["sex_filter"]:
                        continue
                # Age filter
                if "age_max" in rule and patient_age is not None:
                    if patient_age > rule["age_max"]:
                        continue

                # Trigger keywords — all_sections or section text
                full_text = self._get_all_section_text(all_sections or {})
                triggers = rule.get("trigger_keywords", [])
                if triggers and not any(t in full_text.lower() for t in triggers):
                    continue

                # Missing-keyword check
                missing_kw = rule.get("if_missing_keyword", [])
                if missing_kw and any(kw in full_text.lower() for kw in missing_kw):
                    continue  # already documented

                add(rule["question"])

        return questions

    # ------------------------------------------------------------------
    # CONTRADICTION DETECTION
    # ------------------------------------------------------------------

    def detect_contradictions(
        self, all_sections: Dict[str, Any]
    ) -> List[Dict]:
        """
        Run all contradiction checks against the flat sections dict.

        Returns list of dicts: {type, message, severity}
        """
        contradictions: List[Dict] = []

        contradictions.extend(self._check_drug_allergy(all_sections))
        contradictions.extend(self._check_vital_signs(all_sections))
        contradictions.extend(self._check_immunisation_age(all_sections))
        contradictions.extend(self._check_pregnancy_male(all_sections))
        contradictions.extend(self._check_duration_consistency(all_sections))

        return contradictions

    # ------------------------------------------------------------------
    # CONTRADICTION HELPERS
    # ------------------------------------------------------------------

    def _check_drug_allergy(self, sections: Dict) -> List[Dict]:
        """Drug-class-aware allergy vs prescription conflict."""
        results = []
        drug_hx = sections.get("drug_history", {})
        if not drug_hx:
            return results

        # Support both dict-of-data and flat fields
        data = drug_hx if isinstance(drug_hx, dict) else drug_hx.get("data", {})

        allergies_raw = data.get("allergies", "")
        meds_raw = data.get("current_medications", "")

        # Normalise to strings for text-matching
        if isinstance(allergies_raw, list):
            allergy_str = " ".join(
                (a.get("drug", a) if isinstance(a, dict) else str(a))
                for a in allergies_raw
            ).lower()
        else:
            allergy_str = str(allergies_raw).lower()

        if isinstance(meds_raw, list):
            meds_str = " ".join(
                (m.get("drug", m) if isinstance(m, dict) else str(m))
                for m in meds_raw
            ).lower()
        else:
            meds_str = str(meds_raw).lower()

        if not allergy_str or not meds_str:
            return results

        # Check every allergen against every prescribed drug
        allergens = re.findall(r"[\w\-]+", allergy_str)
        prescribed = re.findall(r"[\w\-]+", meds_str)

        flagged = set()
        for allergen in allergens:
            for drug in prescribed:
                if _drugs_conflict(allergen, drug) and (allergen, drug) not in flagged:
                    flagged.add((allergen, drug))
                    results.append({
                        "type": "contradiction",
                        "message": (
                            f"⚠ SAFETY ALERT: Patient has a documented allergy to "
                            f"'{allergen}' but has been prescribed '{drug}'. "
                            f"Please verify and resolve before proceeding."
                        ),
                        "severity": "high",
                    })

        return results

    def _check_vital_signs(self, sections: Dict) -> List[Dict]:
        """Flag physiologically impossible vital sign values."""
        results = []
        exam = sections.get("physical_examination", {})
        if not exam:
            return results

        data = exam if isinstance(exam, dict) else exam.get("data", {})
        vitals_raw = data.get("vital_signs", data)  # some templates embed vitals at top level

        def _to_float(val) -> Optional[float]:
            try:
                if isinstance(val, dict):
                    return float(val.get("value") or val.get("result") or 0)
                return float(str(val).split()[0])
            except (ValueError, TypeError):
                return None

        checks = [
            ("pulse_rate",        30, 250, "Heart rate", "bpm",
             "Physiologic range 30–250 bpm"),
            ("respiratory_rate",   4,  70, "Respiratory rate", "breaths/min",
             "Physiologic range 4–70 breaths/min"),
            ("temperature",       32,  43, "Temperature", "°C",
             "Survivable range 32–43 °C"),
            ("oxygen_saturation",  50, 100, "SpO₂", "%",
             "SpO₂ cannot exceed 100%"),
        ]

        for field, lo, hi, label, unit, reason in checks:
            raw = vitals_raw.get(field) if isinstance(vitals_raw, dict) else None
            if raw is None:
                raw = data.get(field)
            if raw is None:
                continue
            val = _to_float(raw)
            if val is not None and not (lo <= val <= hi):
                results.append({
                    "type": "warning",
                    "message": (
                        f"{label} of {val} {unit} is outside the expected range. "
                        f"{reason}. Please verify the measurement."
                    ),
                    "severity": "high",
                })

        # Systolic > Diastolic check
        bp_raw = vitals_raw.get("blood_pressure", "") if isinstance(vitals_raw, dict) else ""
        bp_str = str(bp_raw)
        bp_match = re.search(r"(\d+)\s*/\s*(\d+)", bp_str)
        if bp_match:
            systolic = int(bp_match.group(1))
            diastolic = int(bp_match.group(2))
            if systolic <= diastolic:
                results.append({
                    "type": "warning",
                    "message": (
                        f"Blood pressure {systolic}/{diastolic} mmHg: "
                        f"systolic should be greater than diastolic. "
                        f"Please verify the recording."
                    ),
                    "severity": "high",
                })
            if systolic > 300 or diastolic > 200:
                results.append({
                    "type": "warning",
                    "message": (
                        f"Blood pressure {systolic}/{diastolic} mmHg is outside "
                        f"a plausible range. Please verify."
                    ),
                    "severity": "high",
                })

        return results

    def _check_immunisation_age(self, sections: Dict) -> List[Dict]:
        """Paediatric immunisation vs age plausibility."""
        results = []
        demo = sections.get("demographics", {})
        immunisation = sections.get("immunisation_history", {})
        if not demo or not immunisation:
            return results

        demo_data = demo if isinstance(demo, dict) else demo.get("data", {})
        imm_data = immunisation if isinstance(immunisation, dict) else immunisation.get("data", {})

        age = demo_data.get("age")
        try:
            age_val = int(str(age).split()[0])
        except (ValueError, TypeError):
            return results

        vaccines_raw = imm_data.get("vaccines_received", "")
        if isinstance(vaccines_raw, list):
            vaccines_str = " ".join(str(v) for v in vaccines_raw).lower()
        else:
            vaccines_str = str(vaccines_raw).lower()

        # Measles-rubella vaccine given at ≥ 9 months
        if age_val < 9 and any(kw in vaccines_str for kw in
                                ["measles", "mmr", "mr vaccine", "rubella"]):
            results.append({
                "type": "contradiction",
                "message": (
                    f"Immunisation record shows measles/MMR vaccine but patient is "
                    f"{age_val} months old. Measles vaccine (MR-1) is typically first "
                    f"given at 9 months. Please verify."
                ),
                "severity": "high",
            })

        # BCG: given at birth / within first year
        if age_val > 60 and "bcg" in vaccines_str:
            pass  # BCG in older children is not necessarily wrong — no flag

        return results

    def _check_pregnancy_male(self, sections: Dict) -> List[Dict]:
        """Flag if pregnancy is documented for a male patient."""
        results = []
        demo = sections.get("demographics", {})
        obs = sections.get("obstetric_history", {})
        if not demo or not obs:
            return results

        demo_data = demo if isinstance(demo, dict) else demo.get("data", {})
        obs_data = obs if isinstance(obs, dict) else obs.get("data", {})

        gender = str(demo_data.get("gender", "")).lower()
        gravida = obs_data.get("gravida")

        if "male" in gender and gravida:
            try:
                if int(str(gravida)) > 0:
                    results.append({
                        "type": "contradiction",
                        "message": (
                            "Obstetric history documents a gravida > 0 but patient "
                            "is recorded as male. Please verify gender or obstetric data."
                        ),
                        "severity": "high",
                    })
            except (ValueError, TypeError):
                pass

        return results

    def _check_duration_consistency(self, sections: Dict) -> List[Dict]:
        """
        Flag when the presenting complaint duration contradicts the HPI duration.
        Uses numeric extraction — not a simple date-count heuristic.
        """
        results = []
        pc = sections.get("presenting_complaint", {})
        hpc = sections.get("history_presenting_complaint", {})
        if not pc or not hpc:
            return results

        pc_data = pc if isinstance(pc, dict) else pc.get("data", {})
        hpc_data = hpc if isinstance(hpc, dict) else hpc.get("data", {})

        pc_duration = str(pc_data.get("duration", "")).lower()
        hpc_text = str(
            hpc_data.get("detailed_history", "") or
            hpc_data.get("content", "")
        ).lower()

        if not pc_duration or not hpc_text:
            return results

        def _to_days(text: str) -> Optional[int]:
            m = re.search(
                r"(\d+)\s*(day|days|d\b|week|weeks|wk|month|months|mo\b|year|years|yr)",
                text
            )
            if not m:
                return None
            n = int(m.group(1))
            unit = m.group(2)
            if "year" in unit or "yr" in unit:
                return n * 365
            if "month" in unit or "mo" in unit:
                return n * 30
            if "week" in unit or "wk" in unit:
                return n * 7
            return n  # days

        pc_days = _to_days(pc_duration)
        hpc_days = _to_days(hpc_text)

        if pc_days and hpc_days:
            ratio = max(pc_days, hpc_days) / max(min(pc_days, hpc_days), 1)
            if ratio > 4:   # one is more than 4× the other
                results.append({
                    "type": "warning",
                    "message": (
                        f"Duration discrepancy: presenting complaint states "
                        f"approx. {pc_days} day(s) but the history mentions "
                        f"approx. {hpc_days} day(s). Please verify the timeline."
                    ),
                    "severity": "medium",
                })

        return results

    # ------------------------------------------------------------------
    # PRIVATE HELPERS
    # ------------------------------------------------------------------

    @staticmethod
    def _find_section_template(template: Dict, section_name: str) -> Optional[Dict]:
        for s in template.get("sections", []):
            if s.get("name") == section_name:
                return s
        return None

    @staticmethod
    def _text_contains_pain(text: str) -> bool:
        return bool(re.search(
            r"\b(pain|ache|aching|sore|soreness|tender|tenderness|discomfort)\b",
            text, re.IGNORECASE
        ))

    def _check_socrates(self, text: str) -> List[str]:
        """Return questions for any SOCRATES elements absent from *text*."""
        t = text.lower()
        missing = []
        labels = {
            "site":        "Site of pain: where exactly is it located?",
            "onset":       "Onset: was it sudden or gradual? When did it start?",
            "character":   "Character: what does the pain feel like? (sharp / dull / burning / cramping)",
            "radiation":   "Radiation: does the pain spread anywhere?",
            "associations": "Associations: any other symptoms accompanying the pain?",
            "time_course": "Time course: is it constant or does it come and go?",
            "exacerbating": "Exacerbating factors: what makes it worse?",
            "relieving":   "Relieving factors: what makes it better?",
            "severity":    "Severity: rate the pain on a scale of 0–10.",
        }
        for element, question in labels.items():
            keywords = self.SOCRATES_KEYWORDS[element]
            if not any(kw in t for kw in keywords):
                missing.append(question)
        return missing

    @staticmethod
    def _skip_for_sex(field: str, sex: Optional[str]) -> bool:
        """Return True if this field should be skipped based on sex."""
        if not sex:
            return False
        sex_lower = sex.lower()
        female_only = {"lmp", "gravida", "para", "menstrual", "obstetric"}
        if any(f in field for f in female_only) and "male" in sex_lower and "female" not in sex_lower:
            return True
        return False

    @staticmethod
    def _skip_for_age(field: str, age: Optional[int]) -> bool:
        """Return True if this field should be skipped based on age."""
        if age is None:
            return False
        # Don't ask about developmental history for adults
        adult_skip = {"gross_motor", "fine_motor", "speech_language", "birth_weight",
                      "gestation", "neonatal"}
        if any(f in field for f in adult_skip) and age > 18:
            return True
        return False

    @staticmethod
    def _get_all_section_text(all_sections: Dict) -> str:
        """Flatten all section data into a single string for keyword matching."""
        parts = []
        for sec_name, sec_val in all_sections.items():
            if isinstance(sec_val, dict):
                data = sec_val.get("data", sec_val)
                parts.append(" ".join(str(v) for v in data.values() if v))
            elif isinstance(sec_val, str):
                parts.append(sec_val)
        return " ".join(parts)


# ============================================================================
# AI CLARIFIER
# ============================================================================

class AIClarifier:
    """
    Uses Claude to generate additional clarifications when rule-based
    checks find nothing missing.
    """

    SYSTEM_PROMPT = (
        "You are a medical education assistant helping medical students "
        "complete clinical case documentation. Identify missing or incomplete "
        "information in the provided clinical section and generate 1–3 specific, "
        "targeted clarification questions. Be concise and professional. "
        "Return only the questions, one per line, with no numbering or bullets."
    )

    def __init__(self):
        self.client = None
        if ANTHROPIC_AVAILABLE:
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if api_key:
                self.client = anthropic.Anthropic(api_key=api_key)

    def is_available(self) -> bool:
        return self.client is not None

    def generate(
        self,
        section_name: str,
        section_data: Dict,
        section_template: Optional[Dict],
        all_sections: Optional[Dict] = None,
    ) -> ClarificationResult:

        if not self.is_available():
            return ClarificationResult(
                questions=[],
                source="ai",
                confidence=0.0,
                reasoning="AI not available — ANTHROPIC_API_KEY not set",
            )

        prompt = self._build_prompt(section_name, section_data,
                                    section_template, all_sections)
        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1000,
                temperature=0.3,
                system=self.SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.content[0].text if response.content else ""
            questions = [
                q.strip() for q in raw.split("\n")
                if q.strip() and not q.strip().startswith("#")
            ]
            return ClarificationResult(
                questions=questions,
                source="ai",
                confidence=0.8 if questions else 0.3,
                reasoning=f"AI generated {len(questions)} question(s)",
            )
        except Exception as exc:
            return ClarificationResult(
                questions=[],
                source="ai",
                confidence=0.0,
                reasoning=f"AI error: {exc}",
            )

    @staticmethod
    def _build_prompt(
        section_name: str,
        section_data: Dict,
        section_template: Optional[Dict],
        all_sections: Optional[Dict],
    ) -> str:
        title = (section_template or {}).get("title", section_name)
        lines = [f"Review the following clinical section: **{title}**\n"]
        lines.append("Current data:")
        for k, v in section_data.items():
            if v:
                lines.append(f"  - {k}: {v}")

        if all_sections:
            demo = all_sections.get("demographics", {})
            if isinstance(demo, dict):
                d = demo.get("data", demo)
                age = d.get("age")
                sex = d.get("gender") or d.get("sex")
                if age or sex:
                    lines.append(f"\nPatient context: age={age}, sex={sex}")

            pc = all_sections.get("presenting_complaint", {})
            if isinstance(pc, dict):
                d = pc.get("data", pc)
                complaint = d.get("complaint")
                if complaint:
                    lines.append(f"Presenting complaint: {complaint}")

        if section_template:
            lines.append("\nExpected fields:")
            for field in section_template.get("fields", []):
                lines.append(f"  - {field.get('label', field.get('name', ''))}")

        lines.append(
            "\nGenerate 1–3 specific questions for missing or incomplete information. "
            "One question per line. No numbers or bullets."
        )
        return "\n".join(lines)


# ============================================================================
# CLARIFICATION ENGINE  (public API — unchanged)
# ============================================================================

class ClarificationEngine:
    """
    Hybrid clarification engine.

    Flow
    ----
    1. Run rule-based checks.
    2. If rules raise questions → return them (source="rules").
    3. If AI is available and rules found nothing → ask AI (source="ai").
    4. If nothing found → return empty result (source="none").
    """

    def __init__(self, use_ai: bool = True):
        self._rules = RuleBasedClarifier()
        self._ai = AIClarifier() if use_ai else None
        self.use_ai = use_ai and bool(self._ai and self._ai.is_available())

    # ------------------------------------------------------------------
    # PUBLIC API
    # ------------------------------------------------------------------

    def process_section(
        self,
        case_id: str,
        section_name: str,
        section_data: Dict[str, Any],
        template: Dict,
        all_sections: Optional[Dict] = None,
    ) -> ClarificationResult:
        """
        Main entry point called by index.py.

        Returns a ClarificationResult with questions and metadata.
        """
        # ── Extract patient context from all_sections ─────────────────
        patient_age, patient_sex, rotation = self._extract_context(
            all_sections or {}, template
        )

        # ── 1. Rule-based clarifications ──────────────────────────────
        rule_questions = self._rules.generate_clarifications(
            section_name=section_name,
            section_data=section_data,
            template=template,
            all_sections=all_sections,
            patient_age=patient_age,
            patient_sex=patient_sex,
            rotation=rotation,
        )

        # ── 2. Contradiction checks ────────────────────────────────────
        if all_sections:
            for contradiction in self._rules.detect_contradictions(all_sections):
                msg = f"[{contradiction['severity'].upper()}] {contradiction['message']}"
                if msg not in rule_questions:
                    rule_questions.append(msg)

        # ── 3. Return rules result if anything found ───────────────────
        if rule_questions:
            return ClarificationResult(
                questions=rule_questions,
                source="rules",
                confidence=0.9,
                reasoning=f"Found {len(rule_questions)} issue(s) via rule-based analysis",
            )

        # ── 4. AI fallback ─────────────────────────────────────────────
        if self.use_ai:
            section_tmpl = RuleBasedClarifier._find_section_template(
                template, section_name
            )
            ai_result = self._ai.generate(
                section_name=section_name,
                section_data=section_data,
                section_template=section_tmpl,
                all_sections=all_sections,
            )
            if ai_result.questions:
                return ai_result

        # ── 5. Nothing needed ─────────────────────────────────────────
        return ClarificationResult(
            questions=[],
            source="none",
            confidence=1.0,
            reasoning="No clarifications needed — section appears complete",
        )

    def detect_contradictions(
        self, all_sections: Dict[str, Any]
    ) -> List[Dict]:
        """Called directly by index.py /api/clarify/contradictions."""
        return self._rules.detect_contradictions(all_sections)

    def get_ai_status(self) -> Dict:
        """Called by index.py /api/status."""
        return {
            "available": self.use_ai,
            "reason": "AI enabled" if self.use_ai else (
                "AI not available — set ANTHROPIC_API_KEY in .env"
            ),
        }

    # ------------------------------------------------------------------
    # PRIVATE
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_context(
        all_sections: Dict, template: Dict
    ):
        """Pull patient age, sex, and rotation name from available data."""
        rotation = template.get("rotation") or template.get("name")

        demo = all_sections.get("demographics", {})
        demo_data = demo.get("data", demo) if isinstance(demo, dict) else {}

        age_raw = demo_data.get("age")
        try:
            age = int(str(age_raw).split()[0]) if age_raw else None
        except (ValueError, TypeError):
            age = None

        sex = (
            demo_data.get("gender")
            or demo_data.get("sex")
            or ""
        )

        return age, sex or None, rotation or None


# ============================================================================
# SINGLETON
# ============================================================================

_engine: Optional[ClarificationEngine] = None


def get_clarification_engine(use_ai: bool = True) -> ClarificationEngine:
    global _engine
    if _engine is None:
        _engine = ClarificationEngine(use_ai=use_ai)
    return _engine
