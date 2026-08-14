from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
import re
import secrets
import time
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Deque, Dict, Final, List, Optional, Set

# ============================================================
# LOGGING & CENTRALIZED PRE-COMPILED REGEX CACHE
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - UNIFIED_SECURE_GATEWAY - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

GSA_REGEX: Final[Dict[str, re.Pattern]] = {
    "pronominal_purge": re.compile(
        r"\b(i|me|my|mine|myself|we|us|our|ours|ourselves)\b", 
        re.IGNORECASE
    ),
    "syntactic_breach": re.compile(
        r"\b(may|might|could|seems|generally|potentially|likely|perhaps|maybe)\b", 
        re.IGNORECASE
    ),
    "prohibited_abstract_verbs": re.compile(
        r"\b(improve|optimize|enhance|enable|support|strengthen|utilize|leverage)\b", 
        re.IGNORECASE
    ),
    "causal_link": re.compile(
        r"\b(because|due to|driven by|resulting from|caused by)\b", 
        re.IGNORECASE
    ),
    "metric_verification": re.compile(
        r"\b\d+(\.\d+)?%|\b\d+\b"
    )
}

# Pipeline System Constants
DEFAULT_BUDGET_MS: Final[float] = 42.0
MAX_RISK_THRESHOLD: Final[float] = 0.80
LONG_PAYLOAD_THRESHOLD: Final[int] = 500
EPOCH_WINDOW_SECONDS: Final[int] = 60

IDENTITY_TOKENS: Final[Set[str]] = {"i", "me", "my", "we", "us", "our"}
COURTESY_TOKENS: Final[Set[str]] = {"please", "could", "helpful", "assistant", "help"}

IDENTITY_WEIGHT: Final[float] = 0.15
COURTESY_WEIGHT: Final[float] = 0.10
LONG_PAYLOAD_WEIGHT: Final[float] = 0.20

WORKER_COUNT: Final[int] = 4
QUEUE_SIZE: Final[int] = 128


# ============================================================
# DATA MODELS
# ============================================================

@dataclass
class OperationalSnapshot:
    timestamp: datetime
    forecast_volume: float
    actual_volume: float
    containment_rate: float
    repeat_contact_rate: float
    abandonment_rate: float
    delinquency_rate: float
    engagement_rate: float
    staffing_level: float
    metadata: Dict = field(default_factory=dict)


@dataclass(frozen=True)
class EngineResult:
    score: float
    findings: List[str]


DistortionResult = EngineResult
StabilityResult = EngineResult
FragilityResult = EngineResult


@dataclass(frozen=True)
class IntelligenceReport:
    confidence_score: float
    distortion: DistortionResult
    stability: StabilityResult
    fragility: FragilityResult
    executive_summary: List[str]


@dataclass(frozen=True)
class PolicyResult:
    allowed: bool
    status: str
    risk_score: float


@dataclass(frozen=True)
class Telemetry:
    budget_ms: float
    entropy: float
    risk_score: float


@dataclass(frozen=True)
class ExecutionResult:
    status: int
    session_id: str
    telemetry: dict
    forensic_sig: str
    auth_tag: str
    runtime_ms: float
    intelligence_report: dict
    ecp_lifecycle_status: str
    linguistic_metrics: dict


@dataclass
class AttestationJob:
    payload: str
    telemetry: Telemetry
    result_future: asyncio.Future


@dataclass
class ECPState:
    seen_outputs: Deque = field(default_factory=lambda: deque(maxlen=1000))
    retry_counter: int = 0
    last_output_hash: Optional[str] = None
    last_timestamp: float = field(default_factory=time.time)


# ============================================================
# ZERO-TRUST LINGUISTIC SAFETIES (CITADEL INTERCEPTORS)
# ============================================================

class IdentityGate:
    def validate(self, text: str) -> bool:
        return not bool(GSA_REGEX["pronominal_purge"].search(text))


class HedgingGate:
    def validate(self, text: str) -> bool:
        return not bool(GSA_REGEX["syntactic_breach"].search(text))


class CausalityGate:
    def validate(self, text: str) -> bool:
        has_causality = bool(GSA_REGEX["causal_link"].search(text))
        has_metrics = bool(GSA_REGEX["metric_verification"].search(text))
        return has_causality or has_metrics


class StructureNormalizer:
    def normalize(self, text: str) -> str:
        # Strip extraneous whitespace and normalize space layout
        cleaned = " ".join(text.split()).strip()
        return GSA_REGEX["prohibited_abstract_verbs"].sub("use", cleaned)


class KineticGovernor:
    def __init__(self, target_latency_ms: float = 15.0):
        self.target_latency: float = target_latency_ms / 1000.0
        self.constant_coefficient: float = 0.815

    async def calculate_temporal_budget(self, token_payload: str) -> float:
        payload_density = len(token_payload.split())
        computed_delay = (payload_density * 0.002) * self.constant_coefficient
        return max(self.target_latency, min(computed_delay, 0.200))

    async def apply_liturgical_pause(self, delay_duration: float) -> None:
        await asyncio.sleep(delay_duration)


# ============================================================
# STATE TRACKING & LOOP MANAGEMENT SPECIFICATION
# ============================================================

class ECPDeterministicEngine:
    def __init__(self, max_retries: int = 5, max_history: int = 1000):
        self.state = ECPState(seen_outputs=deque(maxlen=max_history))
        self.max_retries = max_retries

    def evaluate(self, output: str) -> bool:
        if not output or not output.strip():
            return False
        return True

    def is_loop(self, output: str) -> bool:
        return output in self.state.seen_outputs

    def record(self, output: str):
        self.state.seen_outputs.append(output)
        self.state.last_output_hash = self._hash(output)
        self.state.last_timestamp = time.time()

    def should_retry(self) -> bool:
        return self.state.retry_counter < self.max_retries

    def increment_retry(self):
        self.state.retry_counter += 1

    def reset_retry(self):
        self.state.retry_counter = 0

    def _hash(self, payload: str) -> str:
        return hashlib.sha256(payload.encode()).hexdigest()

    def run(self, output: str) -> str:
        if self.is_loop(output):
            return "BLOCKED_LOOP"

        if not self.evaluate(output):
            if self.should_retry():
                self.increment_retry()
                return "RETRY"
            return "SYSTEM_ERROR"

        self.record(output)
        self.reset_retry()
        return "ACCEPTED"


# ============================================================
# DOIS SYSTEMS ANALYTICS ENGINE
# ============================================================

class SignalLayer:
    def validate(self, snapshot: OperationalSnapshot) -> None:
        if snapshot.forecast_volume < 0 or snapshot.actual_volume < 0:
            raise ValueError("Volumes cannot be negative.")

        rates = [
            snapshot.containment_rate,
            snapshot.repeat_contact_rate,
            snapshot.abandonment_rate,
            snapshot.delinquency_rate,
            snapshot.engagement_rate,
        ]
        if any(not (0.0 <= r <= 1.0) for r in rates):
            raise ValueError("Rates must be between 0.0 and 1.0.")


class DistortionEngine:
    def evaluate(self, snapshot: OperationalSnapshot) -> DistortionResult:
        score = 0.0
        findings: List[str] = []

        if snapshot.containment_rate > 0.80 and snapshot.repeat_contact_rate > 0.20:
            score += 0.30
            findings.append("Containment may be overstating resolution.")

        if snapshot.actual_volume < snapshot.forecast_volume and snapshot.delinquency_rate > 0.08:
            score += 0.25
            findings.append("Demand suppression suspected.")

        if snapshot.engagement_rate < 0.50 and snapshot.delinquency_rate > 0.05:
            score += 0.20
            findings.append("Borrower disengagement risk rising.")

        return DistortionResult(score=min(score, 1.0), findings=findings)


class StabilityEngine:
    def evaluate(self, history: List[OperationalSnapshot]) -> StabilityResult:
        if len(history) < 2:
            return StabilityResult(score=1.0, findings=["Insufficient history."])

        changes: List[float] = []
        for i in range(1, len(history)):
            prev = history[i - 1].actual_volume
            curr = history[i].actual_volume

            if prev == 0:
                continue

            pct_delta = abs(curr - prev) / prev
            changes.append(pct_delta)

        if not changes:
            return StabilityResult(score=1.0, findings=[])

        avg_change = sum(changes) / len(changes)
        score = max(0.0, 1.0 - avg_change)

        findings: List[str] = []
        if score < 0.70:
            findings.append("Operational volatility elevated.")

        return StabilityResult(score=round(score, 4), findings=findings)


class FragilityEngine:
    def evaluate(self, snapshot: OperationalSnapshot) -> FragilityResult:
        score = 0.0
        findings: List[str] = []

        if snapshot.engagement_rate < 0.40:
            score += 0.30
            findings.append("Behavioral sensitivity elevated.")

        if snapshot.abandonment_rate > 0.10:
            score += 0.25
            findings.append("Channel failure sensitivity elevated.")

        if snapshot.delinquency_rate > 0.10:
            score += 0.30
            findings.append("Portfolio stress increasing.")

        return FragilityResult(score=min(score, 1.0), findings=findings)


class ConfidenceIntegrityEngine:
    def calculate(
        self,
        distortion: DistortionResult,
        stability: StabilityResult,
        fragility: FragilityResult,
    ) -> float:
        return round(
            stability.score
            * (1 - distortion.score)
            * (1 - fragility.score),
            4,
        )


class DOIS:
    def __init__(self, max_history_len: int = 90):
        self.signal_layer = SignalLayer()
        self.distortion_engine = DistortionEngine()
        self.stability_engine = StabilityEngine()
        self.fragility_engine = FragilityEngine()
        self.confidence_engine = ConfidenceIntegrityEngine()

        self.history: List[OperationalSnapshot] = []
        self.max_history_len = max_history_len

    def ingest(self, snapshot: OperationalSnapshot) -> IntelligenceReport:
        self.signal_layer.validate(snapshot)

        self.history.append(snapshot)
        if len(self.history) > self.max_history_len:
            self.history.pop(0)

        distortion = self.distortion_engine.evaluate(snapshot)
        stability = self.stability_engine.evaluate(self.history)
        fragility = self.fragility_engine.evaluate(snapshot)

        confidence = self.confidence_engine.calculate(
            distortion, stability, fragility
        )

        if confidence < 0.30:
            summary = ["Executive confidence: LOW."]
        elif confidence < 0.60:
            summary = ["Executive confidence: MODERATE."]
        else:
            summary = ["Executive confidence: HIGH."]

        all_findings = distortion.findings + stability.findings + fragility.findings
        if all_findings:
            summary.extend([f"Finding: {f}" for f in all_findings])

        return IntelligenceReport(
            confidence_score=confidence,
            distortion=distortion,
            stability=stability,
            fragility=fragility,
            executive_summary=summary,
        )


# ============================================================
# PLATFORM TELEMETRY INTERFACES
# ============================================================

class TelemetryDashboard:
    def __init__(self):
        self.requests = 0
        self.rejected = 0
        self.total_risk = 0.0
        self.latencies: Deque[float] = deque(maxlen=1000)

    def record_request(self, risk: float):
        self.requests += 1
        self.total_risk += risk

    def record_reject(self):
        self.rejected += 1

    def record_latency(self, ms: float):
        self.latencies.append(ms)

    def snapshot(self) -> dict:
        avg_risk = self.total_risk / max(self.requests, 1)
        avg_latency = sum(self.latencies) / max(len(self.latencies), 1)

        return {
            "requests": self.requests,
            "rejected": self.rejected,
            "avg_risk": round(avg_risk, 4),
            "avg_latency_ms": round(avg_latency, 4),
        }


# ============================================================
# COMPREHENSIVE INTELLIGENT ROUTING EDGE ENGINE
# ============================================================

class DeterministicPolicyRuntime:
    def __init__(self, signing_key: bytes, generator_fn: Callable[[str], Awaitable[str]], max_retries: int = 5):
        self._key = signing_key
        self.generator = generator_fn
        self.max_retries = max_retries
        
        self._queue: asyncio.Queue[AttestationJob] = asyncio.Queue(maxsize=QUEUE_SIZE)
        self._dashboard = TelemetryDashboard()
        self._workers_started = False
        
        # Sub-System Deployments
        self.dois = DOIS()
        self.ecp_engine = ECPDeterministicEngine(max_retries=max_retries)
        
        # Interceptor Intersections
        self.identity_gate = IdentityGate()
        self.hedging_gate = HedgingGate()
        self.causality_gate = CausalityGate()
        self.normalizer = StructureNormalizer()
        self.governor = KineticGovernor()
        
        # Global Cache Layers
        self.seen_hashes: Set[str] = set()

    def _tokenize(self, text: str) -> List[str]:
        return text.lower().split()

    def _risk_score(self, tokens: List[str], raw: str) -> float:
        score = 0.0
        if any(t in IDENTITY_TOKENS for t in tokens):
            score += IDENTITY_WEIGHT
        if any(t in COURTESY_TOKENS for t in tokens):
            score += COURTESY_WEIGHT
        if len(raw) > LONG_PAYLOAD_THRESHOLD:
            score += LONG_PAYLOAD_WEIGHT
        return round(score, 4)

    def evaluate_policy(self, raw_input: str) -> PolicyResult:
        if not raw_input.strip():
            return PolicyResult(False, "EMPTY_INPUT_VAL", 1.0)

        tokens = self._tokenize(raw_input)
        risk = self._risk_score(tokens, raw_input)

        if risk >= MAX_RISK_THRESHOLD:
            return PolicyResult(False, "RISK_THRESHOLD_EXCEEDED", risk)

        return PolicyResult(True, "SUCCESS_PASS", risk)

    async def generate_telemetry(self, raw_input: str, risk: float) -> Telemetry:
        entropy = 1.0 + (len(raw_input) * 0.002)
        budget = DEFAULT_BUDGET_MS / max(entropy, 1.0)

        return Telemetry(
            budget_ms=round(budget, 4),
            entropy=round(entropy, 4),
            risk_score=risk
        )

    def _generate_hmac_checksum(self, data: str) -> str:
        """Secure attestation tag generation for downstream layers."""
        return hmac.new(self._key, data.encode("utf-8"), hashlib.sha384).hexdigest()

    async def _attestation_worker(self, worker_id: int):
        while True:
            job = await self._queue.get()
            try:
                epoch_bucket = int(time.time() // EPOCH_WINDOW_SECONDS)
                base = f"{job.payload}|{job.telemetry.entropy}|{job.telemetry.risk_score}|{epoch_bucket}"
                
                sig = hashlib.sha256(base.encode()).hexdigest()
                auth = hmac.new(self._key, sig.encode(), hashlib.sha256).hexdigest()

                job.result_future.set_result((sig, auth))
            except Exception as e:
                job.result_future.set_exception(e)
            finally:
                self._queue.task_done()

    def start_workers(self):
        if self._workers_started:
            return
        for i in range(WORKER_COUNT):
            asyncio.create_task(self._attestation_worker(i))
        self._workers_started = True

    def _apply_backpressure(self) -> float:
        qsize = self._queue.qsize()
        if qsize > QUEUE_SIZE * 0.85:
            return 0.002
        if qsize > QUEUE_SIZE * 0.6:
            return 0.001
        return 0.0

    def _generate_operational_snapshot(self, telemetry: Telemetry, ecp_status: str, audit_meta: dict) -> OperationalSnapshot:
        metrics = self._dashboard.snapshot()
        
        metadata = {
            "ecp_lifecycle_status": ecp_status,
            "retry_count": self.ecp_engine.state.retry_counter,
            "last_output_hash": self.ecp_engine.state.last_output_hash,
            **audit_meta
        }

        return OperationalSnapshot(
            timestamp=datetime.now(timezone.utc),
            forecast_volume=100.0,
            actual_volume=float(metrics["requests"]),
            containment_rate=max(0.0, 1.0 - (metrics["rejected"] / max(metrics["requests"], 1))),
            repeat_contact_rate=0.45 if ecp_status == "BLOCKED_LOOP" else round(min(1.0, telemetry.entropy / 10.0), 4),
            abandonment_rate=round(float(self._queue.qsize()) / QUEUE_SIZE, 4),
            delinquency_rate=telemetry.risk_score,
            engagement_rate=max(0.0, 1.0 - telemetry.risk_score),
            staffing_level=float(WORKER_COUNT),
            metadata=metadata
        )

    # ========================================================
    # EXECUTION RUN LIFE CYCLE
    # ============================================================
    async def execute(self, initial_prompt: str) -> dict:
        self.start_workers()
        start_time = time.perf_counter()
        
        working_prompt = initial_prompt
        clean_output = ""
        ecp_status = "PENDING"
        linguistic_metrics = {}

        # Inference Multi-Pass Feedback Alignment Mechanism
        for attempt in range(1, self.max_retries + 1):
            raw_output = await self.generator(working_prompt)
            clean_output = self.normalizer.normalize(raw_output)
            
            # Layer Check 1: Stateful Engine Loop Analysis Check
            ecp_status = self.ecp_engine.run(clean_output)
            if ecp_status == "BLOCKED_LOOP":
                break
                
            # Layer Check 2: Citadel Integrity Filter Array Validation
            id_ok = self.identity_gate.validate(clean_output)
            bool_hedge = self.hedging_gate.validate(clean_output)
            causal_ok = self.causality_gate.validate(clean_output)
            
            output_hash = hashlib.md5(clean_output.encode("utf-8")).hexdigest()
            is_citadel_loop = output_hash in self.seen_hashes
            self.seen_hashes.add(output_hash)

            linguistic_metrics = {
                "identity_passed": id_ok,
                "hedging_passed": bool_hedge,
                "causality_passed": causal_ok,
                "duplicate_payload": is_citadel_loop,
                "attempt": attempt
            }

            if id_ok and bool_hedge and causal_ok and not is_citadel_loop:
                ecp_status = "ACCEPTED"
                break
            
            # Recalculate Multi-Attempt Backplane Adjustments
            self.ecp_engine.increment_retry()
            if not self.ecp_engine.should_retry():
                ecp_status = "SYSTEM_ERROR"
                break
                
            # Formulate Context Injection Delta Parameters
            failure_reasons = []
            if not id_ok: failure_reasons.append("First-person identifier usage.")
            if not bool_hedge: failure_reasons.append("Subjective hedging / uncertainty.")
            if not causal_ok: failure_reasons.append("Missing objective metrics or causal links.")
            if is_citadel_loop: failure_reasons.append("Generative loop iteration pattern triggered.")
            
            working_prompt = (
                f"{initial_prompt}\n[INSTRUCTIONAL_DELTA]: Prior response failed constraints: "
                f"{', '.join(failure_reasons)} Re-render output."
            )

        # Handle early system exceptions and intercepts
        if ecp_status in ("BLOCKED_LOOP", "SYSTEM_ERROR", "RETRY"):
            self._dashboard.record_request(1.0)
            self._dashboard.record_reject()
            
            fallback_telemetry = Telemetry(budget_ms=0.0, entropy=1.0, risk_score=1.0)
            snapshot = self._generate_operational_snapshot(fallback_telemetry, ecp_status, {"err": "gate_intercept"})
            intelligence_report = self.dois.ingest(snapshot)
            
            return {
                "status": 422 if ecp_status == "BLOCKED_LOOP" else 400,
                "error": f"GATEWAY_INTEGRITY_INTERCEPT: {ecp_status}",
                "ecp_lifecycle_status": ecp_status,
                "intelligence_report": asdict(intelligence_report),
                "runtime_ms": round((time.perf_counter() - start_time) * 1000, 2)
            }

        # Step 3: Traditional Policy Optimization Processing
        policy = self.evaluate_policy(clean_output)
        self._dashboard.record_request(policy.risk_score)

        if not policy.allowed:
            self._dashboard.record_reject()
            return {
                "status": 400,
                "error": f"POLICY_VIOLATION: {policy.status}",
                "risk_score": policy.risk_score,
                "ecp_lifecycle_status": ecp_status
            }

        # Step 4: Governor Throttle Computation Integration
        telemetry = await self.generate_telemetry(clean_output, policy.risk_score)
        delay = await self.governor.calculate_temporal_budget(clean_output)
        await self.governor.apply_liturgical_pause(delay)

        # Step 5: Secure Execution Attestation Tasks Backpressure Execution
        future: asyncio.Future = asyncio.get_event_loop().create_future()
        job = AttestationJob(payload=clean_output, telemetry=telemetry, result_future=future)

        if self._queue.full():
            await asyncio.sleep(self._apply_backpressure())

        await self._queue.put(job)
        forensic_sig, auth_tag = await future

        runtime_ms = (time.perf_counter() - start_time) * 1000
        self._dashboard.record_latency(runtime_ms)

        # Step 6: Multi-Dimensional DOIS Analytics Metrics Ingestion
        snapshot = self._generate_operational_snapshot(telemetry, ecp_status, {"status": "SUCCESS"})
        intelligence_report = self.dois.ingest(snapshot)

        result = ExecutionResult(
            status=200,
            session_id=f"DPR-{secrets.token_hex(4).upper()}",
            telemetry=asdict(telemetry),
            forensic_sig=forensic_sig,
            auth_tag=auth_tag,
            runtime_ms=round(runtime_ms, 4),
            intelligence_report=asdict(intelligence_report),
            ecp_lifecycle_status=ecp_status,
            linguistic_metrics=linguistic_metrics
        )

        logger.info(
            "session=%s status=%s ecp_state=%s confidence=%s pause_ms=%s attempts=%s",
            result.session_id, result.status, result.ecp_lifecycle_status,
            intelligence_report.executive_summary[0], round(delay * 1000, 2),
            linguistic_metrics.get("attempt", 1)
        )

        return asdict(result)

    def metrics(self) -> dict:
        return self._dashboard.snapshot()


# ============================================================
# RUNNER SANDBOX VALIDATION
# ============================================================

async def mock_inference_gateway(prompt: str) -> str:
    # Simulates an alignment feedback condition loop
    if "compliant" in prompt.lower():
        return "System performance remains steady because local token consumption decreased by 22%."
    else:
        return "I think we can optimize the pipeline to look much better."

async def main():
    signing_key = b"GSA_ADAMANTIUM_CORE_STASIS_SIGNATURE_815"
    runtime = DeterministicPolicyRuntime(signing_key=signing_key, generator_fn=mock_inference_gateway)

    print("--- Execution 1: Triggers Interceptor Contextual Correction Loops ---")
    res_1 = await runtime.execute("Process standard network infrastructure analysis matrix.")
    print(f"Status: {res_1.get('status') or res_1.get('error')}")
    if "intelligence_report" in res_1:
        print(f"Executive Summary Summary: {res_1['intelligence_report']['executive_summary']}\n")

    print("--- Execution 2: Zero-Trust Compliant Structural Formats ---")
    res_2 = await runtime.execute("Generate a compliant status report metrics profile.")
    print(f"Session Id: {res_2.get('session_id')}")
    print(f"Total Runtime: {res_2.get('runtime_ms')} ms")
    print(f"Linguistic Diagnostics: {res_2.get('linguistic_metrics')}")
    print(f"Executive Summary Summary: {res_2['intelligence_report']['executive_summary']}")

if __name__ == "__main__":
    asyncio.run(main())