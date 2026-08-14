"""Boundary Gate - validates inbound requests."""
from datetime import datetime, timezone
from perceive_kernel import PolicyOutput, Provenance

def boundary_gate_adapter(request) -> PolicyOutput:
    """Check if request is well-formed and authorized."""
    violations = []
    
    if not request.request_id:
        violations.append("Missing request_id")
    if not request.request_type:
        violations.append("Missing request_type")
    if not request.actor_id:
        violations.append("Missing actor_id")
    
    # Check request type is known
    valid_types = {"escalate_patient", "modify_rule", "export_data", "emergency_override"}
    if request.request_type not in valid_types:
        violations.append(f"Unknown request_type: {request.request_type}")
    
    approved = len(violations) == 0
    
    return PolicyOutput(
        gate_name="boundary_gate",
        approved=approved,
        confidence=0.95 if approved else 0.9,
        violation_details=violations,
        timestamp=datetime.now(timezone.utc),
        provenance=Provenance("system", "boundary", "structural_validation"),
    )
