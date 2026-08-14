"""Invariant Validator - ensures state consistency."""
from datetime import datetime, timezone
from perceive_kernel import PolicyOutput, Provenance
from policy_engine import GovernanceInvariants

def invariant_validator_adapter(request) -> PolicyOutput:
    """Validate governance invariants hold."""
    violations = []
    
    # Check invariants
    checks = [
        GovernanceInvariants.audit_trail_immutable(),
        GovernanceInvariants.manifest_versioned(),
        GovernanceInvariants.gates_unanimous(),
        GovernanceInvariants.decisions_replay_deterministic(),
    ]
    
    for passed, message in checks:
        if not passed:
            violations.append(message)
    
    approved = len(violations) == 0
    
    return PolicyOutput(
        gate_name="invariant_validator",
        approved=approved,
        confidence=0.99 if approved else 0.85,
        violation_details=violations,
        timestamp=datetime.now(timezone.utc),
        provenance=Provenance("system", "invariants", "consistency_check"),
    )
