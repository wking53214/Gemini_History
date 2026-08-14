"""
Adversarial Adapter
===================

Checks if input vitals could be adversarial or unrealistic.
Guards against sensor failures, spoofing, data quality issues.
Confidence is reduced when adversarial signals detected.
"""

from datetime import datetime, timezone
from observe_engine import RiskOutput


def adversarial_adapter(vitals) -> RiskOutput:
    """
    Adversarial robustness check on input vitals.

    Detects:
    - Physiologically impossible values
    - Sensor failures (constant values, out-of-range)
    - Synthetic/spoofed patterns
    - Data quality issues

    Args:
        vitals: VitalsSnapshot

    Returns:
        RiskOutput with adversarial risk_score
    """

    triggered_rules = []
    risk_score = 0.0

    # Check 1: Out-of-range values
    if vitals.heart_rate < 0 or vitals.heart_rate > 250:
        triggered_rules.append(f"ADVERSARIAL: Heart rate {vitals.heart_rate} is out of physiological range")
        risk_score += 0.5

    if vitals.oxygen_saturation < 0 or vitals.oxygen_saturation > 100:
        triggered_rules.append(f"ADVERSARIAL: O2 saturation {vitals.oxygen_saturation}% is out of range")
        risk_score += 0.5

    if vitals.respiratory_rate < 0 or vitals.respiratory_rate > 120:
        triggered_rules.append(f"ADVERSARIAL: Respiratory rate {vitals.respiratory_rate} is out of range")
        risk_score += 0.5

    if vitals.temperature < 30 or vitals.temperature > 43:
        triggered_rules.append(f"ADVERSARIAL: Temperature {vitals.temperature}°C is out of range")
        risk_score += 0.4

    # Check 2: Constant values (sensor failure)
    previous_o2 = vitals.context.get("previous_o2")
    previous_hr = vitals.context.get("previous_hr")
    previous_rr = vitals.context.get("previous_rr")

    if previous_o2 is not None and abs(vitals.oxygen_saturation - previous_o2) < 0.01:
        triggered_rules.append("ADVERSARIAL: O2 saturation unchanged from previous reading (possible sensor failure)")
        risk_score += 0.3

    if previous_hr is not None and abs(vitals.heart_rate - previous_hr) < 0.01:
        triggered_rules.append("ADVERSARIAL: Heart rate unchanged from previous reading (possible sensor failure)")
        risk_score += 0.3

    # Check 3: Perfectly smooth patterns (synthetic)
    # Real vitals have noise; perfectly smooth patterns are suspicious
    historical_data = vitals.context.get("historical_o2", [])
    if len(historical_data) > 10:
        # Calculate variance in last 10 readings
        variance = sum(
            (historical_data[i] - historical_data[i - 1])**2
            for i in range(1, len(historical_data))
        ) / len(historical_data)

        if variance < 0.001:  # Too smooth
            triggered_rules.append(
                "ADVERSARIAL: O2 pattern is too smooth/regular (suspicious synthetic pattern)"
            )
            risk_score += 0.2

    # Check 4: Impossible vital relationships
    # E.g., very low O2 but normal HR (unusual, suggests spoofing)
    if vitals.oxygen_saturation < 85 and vitals.heart_rate < 100:
        triggered_rules.append(
            "ADVERSARIAL: Low O2 with normal HR (physiologically unusual, "
            "could indicate spoofed values)"
        )
        risk_score += 0.2

    # Check 5: Data consistency
    # No measurement should jump more than 30% in 60 seconds
    if previous_o2 is not None:
        o2_pct_change = abs(vitals.oxygen_saturation - previous_o2) / max(previous_o2, 0.1)
        if o2_pct_change > 0.30:
            triggered_rules.append(
                f"ADVERSARIAL: O2 jumped {o2_pct_change*100:.0f}% in one reading "
                "(suspicious, possible sensor glitch)"
            )
            risk_score += 0.2

    # Cap risk score
    risk_score = min(risk_score, 1.0)

    # Confidence: lower if adversarial signals detected
    confidence = 0.9 if risk_score == 0.0 else (0.3 + (0.6 * (1.0 - risk_score)))

    if risk_score > 0:
        triggered_rules.insert(
            0,
            f"OVERALL_ADVERSARIAL_RISK: {risk_score:.2f} (input quality concern)"
        )

    # Regime classification
    regime_probs = {
        "stable": max(0.1, 1.0 - risk_score),
        "caution": min(0.3, risk_score * 0.3),
        "warning": min(0.3, risk_score * 0.5),
        "critical": min(0.2, risk_score * 0.8),
    }

    # Normalize
    total = sum(regime_probs.values())
    if total > 0:
        regime_probs = {k: v / total for k, v in regime_probs.items()}

    return RiskOutput(
        engine_name="adversarial",
        risk_score=risk_score,
        confidence=confidence,
        regime_classification=regime_probs,
        triggered_rules=triggered_rules,
        timestamp=datetime.now(timezone.utc),
    )
