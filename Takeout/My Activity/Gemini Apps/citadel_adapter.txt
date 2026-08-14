"""Citadel - linguistic intent validation and clarity checks."""
from datetime import datetime, timezone
from perceive_kernel import PolicyOutput, Provenance

def citadel_adapter(request) -> PolicyOutput:
    """Validate request intent is clear and justified."""
    violations = []
    
    context = request.context or {}
    
    # Check justification provided
    justification = context.get("justification", "")
    if not justification or len(justification.strip()) < 10:
        violations.append("Insufficient justification provided (minimum 10 characters)")
    
    # Check for clarity of intent
    if request.request_type == "emergency_override":
        if not context.get("emergency_reason"):
            violations.append("Emergency override requires explicit reason")
    
    # Check for hedging language (indirect requests)
    if "maybe" in justification.lower() or "might" in justification.lower():
        violations.append("Request lacks clarity (hedging language detected)")
    
    # Validate request type matches context
    request_type = request.request_type
    has_matching_context = False
    
    if request_type == "escalate_patient" and "severity" in context:
        has_matching_context = True
    elif request_type == "modify_rule" and "rule_id" in context:
        has_matching_context = True
    elif request_type == "export_data" and "export_type" in context:
        has_matching_context = True
    elif request_type == "emergency_override" and "emergency_reason" in context:
        has_matching_context = True
    
    if not has_matching_context and request_type != "unknown":
        violations.append(f"Request type '{request_type}' missing required context")
    
    approved = len(violations) == 0
    
    return PolicyOutput(
        gate_name="citadel",
        approved=approved,
        confidence=0.85 if approved else 0.80,
        violation_details=violations,
        timestamp=datetime.now(timezone.utc),
        provenance=Provenance("system", "citadel", "intent_validation"),
    )
