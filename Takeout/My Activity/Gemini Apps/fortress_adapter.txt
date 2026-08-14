"""Fortress - content safety and containment checks."""
from datetime import datetime, timezone
from perceive_kernel import PolicyOutput, Provenance

def fortress_adapter(request) -> PolicyOutput:
    """Check for unsafe or restricted content in request."""
    violations = []
    
    # Check context for dangerous operations
    context = request.context or {}
    
    # Prevent unrestricted data access
    if context.get("request_all_data"):
        violations.append("Unrestricted data access not permitted")
    
    # Check for rule modifications that would weaken safety
    if request.request_type == "modify_rule":
        rule_changes = context.get("changes", {})
        if rule_changes.get("disable_audit"):
            violations.append("Cannot disable audit logging")
        if rule_changes.get("disable_gates"):
            violations.append("Cannot disable policy gates")
    
    # Check for attempts to bypass policies
    if context.get("bypass_approval"):
        violations.append("Bypass of approval process not permitted")
    
    approved = len(violations) == 0
    
    return PolicyOutput(
        gate_name="fortress",
        approved=approved,
        confidence=0.92 if approved else 0.88,
        violation_details=violations,
        timestamp=datetime.now(timezone.utc),
        provenance=Provenance("system", "fortress", "content_safety"),
    )
