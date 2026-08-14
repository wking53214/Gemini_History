"""
Clinical Policy Engine
======================

Pediatric-specific thresholds, rules, and decision logic.
All values evidence-based (PEWS, pediatric literature).
"""

from dataclasses import dataclass
from typing import Dict, List

# ============================================================
# PEDIATRIC VITAL SIGN NORMS (AGE-ADJUSTED)
# ============================================================

@dataclass
class AgeGroup:
    """Represents age-specific vital sign ranges."""
    name: str
    age_min_months: int
    age_max_months: int
    hr_normal: tuple  # (min, max)
    rr_normal: tuple
    o2_normal: tuple
    temp_normal: tuple


# Evidence-based pediatric norms (simplified)
PEDIATRIC_NORMS = [
    AgeGroup(
        name="Neonatal",
        age_min_months=0,
        age_max_months=3,
        hr_normal=(100, 160),
        rr_normal=(30, 60),
        o2_normal=(95, 100),
        temp_normal=(36.5, 37.5),
    ),
    AgeGroup(
        name="Infant",
        age_min_months=3,
        age_max_months=12,
        hr_normal=(90, 150),
        rr_normal=(25, 50),
        o2_normal=(95, 100),
        temp_normal=(36.5, 37.5),
    ),
    AgeGroup(
        name="Toddler",
        age_min_months=12,
        age_max_months=36,
        hr_normal=(80, 130),
        rr_normal=(20, 40),
        o2_normal=(95, 100),
        temp_normal=(36.5, 37.5),
    ),
    AgeGroup(
        name="Child",
        age_min_months=36,
        age_max_months=144,
        hr_normal=(70, 110),
        rr_normal=(18, 30),
        o2_normal=(95, 100),
        temp_normal=(36.5, 37.5),
    ),
]


# ============================================================
# ESCALATION THRESHOLDS
# ============================================================

@dataclass
class EscalationThresholds:
    """Risk score thresholds for regime classification."""
    stable_max: float = 0.25
    caution_max: float = 0.50
    warning_max: float = 0.75
    critical_min: float = 0.75


ESCALATION_THRESHOLDS = EscalationThresholds()


# ============================================================
# CLINICAL RULES (HEURISTIC)
# ============================================================

class ClinicalRules:
    """Evidence-based heuristic rules for pediatric risk assessment."""

    # Critical O2 saturation (SpO2)
    @staticmethod
    def critical_o2(o2_sat: float) -> tuple[bool, str]:
        """SpO2 < 88% = critical hypoxemia (PEWS score: 3 points)."""
        if o2_sat < 88:
            return True, f"Critical O2: {o2_sat}% (threshold 88%)"
        return False, ""

    # Severe tachycardia
    @staticmethod
    def severe_tachycardia(hr: float, age_months: int) -> tuple[bool, str]:
        """Heart rate > 95th percentile for age."""
        age_group = next(
            (ag for ag in PEDIATRIC_NORMS if ag.age_min_months <= age_months < ag.age_max_months),
            PEDIATRIC_NORMS[-1],
        )
        threshold = age_group.hr_normal[1] + 30  # 95th percentile + buffer
        if hr > threshold:
            return True, f"Severe tachycardia: {hr} bpm (age-adjusted threshold {threshold})"
        return False, ""

    # Severe bradycardia
    @staticmethod
    def severe_bradycardia(hr: float, age_months: int) -> tuple[bool, str]:
        """Heart rate < 5th percentile for age."""
        age_group = next(
            (ag for ag in PEDIATRIC_NORMS if ag.age_min_months <= age_months < ag.age_max_months),
            PEDIATRIC_NORMS[-1],
        )
        threshold = age_group.hr_normal[0] - 20  # 5th percentile - buffer
        if hr < threshold:
            return True, f"Severe bradycardia: {hr} bpm (age-adjusted threshold {threshold})"
        return False, ""

    # Severe tachypnea
    @staticmethod
    def severe_tachypnea(rr: float, age_months: int) -> tuple[bool, str]:
        """Respiratory rate > 95th percentile for age (PEWS: 3 points)."""
        age_group = next(
            (ag for ag in PEDIATRIC_NORMS if ag.age_min_months <= age_months < ag.age_max_months),
            PEDIATRIC_NORMS[-1],
        )
        threshold = age_group.rr_normal[1] + 15
        if rr > threshold:
            return True, f"Severe tachypnea: {rr} bpm (age-adjusted threshold {threshold})"
        return False, ""

    # Fever
    @staticmethod
    def fever(temp: float) -> tuple[bool, str]:
        """Temperature > 39.5°C = significant fever."""
        if temp > 39.5:
            return True, f"Fever: {temp}°C (threshold 39.5°C)"
        return False, ""

    # Hypothermia
    @staticmethod
    def hypothermia(temp: float) -> tuple[bool, str]:
        """Temperature < 35°C = hypothermia (danger sign)."""
        if temp < 35.0:
            return True, f"Hypothermia: {temp}°C (threshold 35.0°C)"
        return False, ""

    # Trending deterioration
    @staticmethod
    def trending_deterioration(
        current_o2: float,
        previous_o2: float,
        current_hr: float,
        previous_hr: float,
    ) -> tuple[bool, str]:
        """
        Multiple vital signs trending in wrong direction simultaneously.
        Indicates systemic deterioration (not isolated measurement).
        """
        o2_drop = previous_o2 - current_o2 > 3  # >3% drop
        hr_rise = current_hr - previous_hr > 20  # >20 bpm rise
        both_bad = o2_drop and hr_rise

        if both_bad:
            return True, (
                f"Trending deterioration: O2 dropping ({previous_o2} → {current_o2}), "
                f"HR rising ({previous_hr} → {current_hr})"
            )
        return False, ""

    @staticmethod
    def all_rules(
        hr: float,
        o2_sat: float,
        rr: float,
        temp: float,
        age_months: int = 36,  # default to toddler
        previous_o2: float = None,
        previous_hr: float = None,
    ) -> tuple[float, List[str]]:
        """
        Run all heuristic rules and return aggregated risk score.
        Returns: (risk_score, list_of_triggered_rules)
        """
        triggered_rules = []
        risk_accumulator = 0.0

        # Run all rules
        rules_to_check = [
            (ClinicalRules.critical_o2(o2_sat), 0.8),
            (ClinicalRules.severe_tachycardia(hr, age_months), 0.5),
            (ClinicalRules.severe_bradycardia(hr, age_months), 0.5),
            (ClinicalRules.severe_tachypnea(rr, age_months), 0.4),
            (ClinicalRules.fever(temp), 0.3),
            (ClinicalRules.hypothermia(temp), 0.5),
        ]

        if previous_o2 is not None and previous_hr is not None:
            rules_to_check.append(
                (ClinicalRules.trending_deterioration(
                    o2_sat, previous_o2, hr, previous_hr
                ), 0.6)
            )

        for (triggered, rule_text), weight in rules_to_check:
            if triggered:
                triggered_rules.append(rule_text)
                risk_accumulator += weight

        # Cap at 1.0
        return min(risk_accumulator, 1.0), triggered_rules


# ============================================================
# REGIME CLASSIFICATION
# ============================================================

class RegimeClassifier:
    """Maps risk score to clinical regime."""

    @staticmethod
    def classify(risk_score: float) -> str:
        """
        Classify risk score into regime.
        Risk score aggregates heuristic violations.
        """
        if risk_score >= ESCALATION_THRESHOLDS.critical_min:
            return "critical"
        elif risk_score >= ESCALATION_THRESHOLDS.warning_max:
            return "warning"
        elif risk_score >= ESCALATION_THRESHOLDS.caution_max:
            return "caution"
        else:
            return "stable"

    @staticmethod
    def regime_probabilities(risk_score: float) -> Dict[str, float]:
        """
        Convert risk score to regime probability distribution.
        Lower risk → higher probability of stable regime.
        """
        regime = RegimeClassifier.classify(risk_score)

        # Create probability distribution centered on classified regime
        if regime == "critical":
            return {
                "stable": 0.05,
                "caution": 0.10,
                "warning": 0.25,
                "critical": 0.60,
            }
        elif regime == "warning":
            return {
                "stable": 0.10,
                "caution": 0.15,
                "warning": 0.60,
                "critical": 0.15,
            }
        elif regime == "caution":
            return {
                "stable": 0.20,
                "caution": 0.60,
                "warning": 0.15,
                "critical": 0.05,
            }
        else:  # stable
            return {
                "stable": 0.85,
                "caution": 0.10,
                "warning": 0.04,
                "critical": 0.01,
            }


# ============================================================
# DRIFT DETECTION THRESHOLDS
# ============================================================

class DriftThresholds:
    """Thresholds for detecting model degradation."""
    o2_sat_drift: float = 2.0  # SpO2 shifting by >2% baseline
    hr_drift: float = 15.0  # HR shifting by >15 bpm
    rr_drift: float = 5.0  # RR shifting by >5 breaths/min
    temp_drift: float = 0.5  # Temp shifting by >0.5°C


# ============================================================
# BEHAVIORAL VACCINE PATTERNS
# ============================================================

class BehavioralVaccine:
    """
    Learned patterns of benign vs dangerous trajectories.
    Used for pattern recognition without explicit rules.
    """

    # Benign patterns (low risk despite elevated vitals)
    BENIGN_PATTERNS = [
        {
            "name": "fever_response",
            "description": "High temp + high HR, but stable O2 and alert",
            "features": ["temp_elevated", "hr_elevated", "o2_normal", "alert"],
            "risk_reduction": 0.2,
        },
        {
            "name": "crying_baby",
            "description": "Isolated tachycardia + tachypnea, alert, short duration",
            "features": ["hr_elevated", "rr_elevated", "o2_normal", "duration_short"],
            "risk_reduction": 0.3,
        },
    ]

    # Dangerous patterns (high risk indicators)
    DANGEROUS_PATTERNS = [
        {
            "name": "septic_shock",
            "description": "O2 drop + HR rise + poor perfusion",
            "features": ["o2_dropping", "hr_rising", "bp_low", "delayed_capillary_refill"],
            "risk_multiplier": 1.5,
        },
        {
            "name": "respiratory_distress",
            "description": "RR rising + O2 dropping + accessory muscle use",
            "features": ["rr_rising", "o2_dropping", "retractions", "grunting"],
            "risk_multiplier": 1.4,
        },
    ]

    @staticmethod
    def apply_pattern(risk_score: float, pattern_name: str) -> float:
        """Apply pattern modifier to risk score."""
        for pattern in BehavioralVaccine.BENIGN_PATTERNS:
            if pattern["name"] == pattern_name:
                return max(0.0, risk_score - pattern["risk_reduction"])

        for pattern in BehavioralVaccine.DANGEROUS_PATTERNS:
            if pattern["name"] == pattern_name:
                return min(1.0, risk_score * pattern["risk_multiplier"])

        return risk_score


# ============================================================
# PEDIATRIC THRESHOLDS (SUMMARY)
# ============================================================

POLICY_SUMMARY = {
    "critical_o2_threshold": 88.0,
    "fever_threshold": 39.5,
    "hypothermia_threshold": 35.0,
    "dwell_count": 2,
    "escalation_lock_duration_seconds": 300,
    "pediatric_norms": [
        {
            "age_group": ag.name,
            "hr": ag.hr_normal,
            "rr": ag.rr_normal,
            "o2": ag.o2_normal,
        }
        for ag in PEDIATRIC_NORMS
    ],
}
