"""MicroPatch - emergency override and exception handling."""
from datetime import datetime, timezone
from perceive_kernel import PolicyOutput, Provenance
from policy_engine import EmergencyOverridePolicy

def micropatch_adapter(request) -> PolicyOutput:
    """Evaluate emergency override requests."""
    violations = []
    
    # Only evaluate for emergency override requests
    if request.request_type != "emergency_override":
        # Not applicable to this request
        return PolicyOutput(
            gate_name="micropatch",
            approved=True,
            confidence=1.0,
            violation_details=["MicroPatch not applicable to non-emergency requests"],
            timestamp=datetime.now(timezone.utc),
            provenance=Provenance("system", "micropatch", "not_applicable"),
        )
    
    context = request.context or {}
    
    # Use policy engine to evaluate override
    override_type = context.get("override_type", "unknown")
    justification = context.get("emergency_reason", "")
    has_approval = context.get("physician_approved", False)
    can_notify = context.get("can_notify_stakeholders", False)
    
    approved, policy_violations = EmergencyOverridePolicy.can_override(
        override_type=override_type,
        justification=justification,
        has_physician_approval=has_approval,
        can_notify=can_notify,
    )
    
    violations.extend(policy_violations)
    
    # Additional MicroPatch checks
    if override_type == "patient_safety":
        # Patient safety overrides require immediate escalation
        if not context.get("escalated_to_physician"):
            violations.append("Patient safety override must be escalated to physician")
    
    approved = len(violations) == 0
    
    return PolicyOutput(
        gate_name="micropatch",
        approved=approved,
        confidence=0.90 if approved else 0.85,
        violation_details=violations,
        timestamp=datetime.now(timezone.utc),
        provenance=Provenance("system", "micropatch", "emergency_evaluation"),
    )
