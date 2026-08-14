"""
clinical_vitals_adapter.py

Clinical vitals-monitoring adapters (pediatric early-warning context).

This module depends on the clinical data_contracts (dc) only. It shares no
symbols with the vehicle stack, keeping the 510(k)/clinical audit surface free
of automotive code paths. The nonlinear-dynamics helpers are duplicated here
(rather than imported from a shared lib) deliberately: hard domain isolation is
worth more than DRY when the two domains are independently certified.

Adapters
--------
vitals_bounds_adapter : age-aware HR/RR range check (PEWS-style)
    Deterministic, cheap. Scores excursions outside the age-band reference.

physiologic_complexity_adapter : HR/RR complexity index
    Computes phase coupling + largest Lyapunov exponent of the coupling.
    Reported as INFORMATIONAL by default -- see the risk-mapping caveat in the
    function docstring. The "positive Lyapunov = bad" mapping that the vehicle
    side uses is NOT clinically established and is intentionally not applied
    here until calibrated.

Cross-domain enhancements (folded in from the adapter family)
-------------------------------------------------------------
physiological_validity_gate : artifact pre-filter -- rejects physiologically
    impossible readings before they can score (black-hole validity gate).
vote_sources / assess_data_quality : multi-source sensor agreement -- disagreement
    flags artifact and lowers confidence (flight-control redundancy/voting).
vitals_rate_adapter : rate-of-change alarm -- a vital moving too fast is flagged
    even while still in band (power-grid ROCOF).
fuse_clinical_risk : confidence-weighted fusion that abstains when inputs are too
    thin, so trust is reported rather than assumed (black-hole inverted semantics).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

import numpy as np
import pywt
from scipy.spatial import KDTree

import data_contracts as dc

# ---------------------------------------------------------------------------
# Age-band reference ranges
# ---------------------------------------------------------------------------
# Approximate normal *awake* vital-sign ranges by age band.
# Source-class: standard pediatric references (PALS-style).
#
# *** THESE ARE DEFAULTS ONLY. Replace with the ranges in your institution's
# validated PEWS protocol and reconcile them with the thresholds already used
# by the 7-engine sepsis detector so the two layers cannot disagree. Have the
# final numbers signed off clinically before deployment. ***
PEDIATRIC_VITALS_REFERENCE: Dict[str, Dict[str, Tuple[float, float]]] = {
    #                         heart_rate (bpm)    respiratory_rate (breaths/min)
    "neonate":     {"hr": (100.0, 205.0), "rr": (30.0, 60.0)},   # 0-1 mo
    "infant":      {"hr": (100.0, 180.0), "rr": (30.0, 53.0)},   # 1-12 mo
    "toddler":     {"hr": (98.0, 140.0),  "rr": (22.0, 37.0)},   # 1-3 yr
    "preschool":   {"hr": (80.0, 120.0),  "rr": (20.0, 28.0)},   # 3-5 yr
    "school":      {"hr": (75.0, 118.0),  "rr": (18.0, 25.0)},   # 6-11 yr
    "adolescent":  {"hr": (60.0, 100.0),  "rr": (12.0, 20.0)},   # 12+ yr
}

# ---------------------------------------------------------------------------
# Physiologic sanity limits (validity pre-gate) + rate-of-change limits
# ---------------------------------------------------------------------------
# Readings outside these are physiologically impossible -> treat as ARTIFACT and
# exclude from scoring before they reach the 7-engine fusion. Deliberately wider
# than the age-band ALARM ranges: this gate rejects garbage, it does not raise
# clinical alarms. *** Illustrative defaults -- confirm clinically. ***
PHYSIOLOGIC_LIMITS: Dict[str, Tuple[float, float]] = {
    "heart_rate":       (20.0, 300.0),   # bpm
    "respiratory_rate": (4.0, 120.0),    # breaths/min
    "spo2":             (50.0, 100.0),   # %  (optional, from context)
    "temp_c":           (25.0, 44.0),    # deg C (optional, from context)
}

# Maximum trustworthy |change| in a vital across the analysis window. A move
# faster than this -- in EITHER direction -- is the ROCOF analog: a rate alarm
# in its own right, even while the absolute value is still in band. A rapid
# bradycardic fall and a rapid tachy climb both matter, hence magnitude.
# *** Illustrative defaults; calibrate to your sampling window + clinical input. ***
RATE_LIMITS_PER_WINDOW: Dict[str, float] = {
    "heart_rate":       30.0,   # bpm across the window
    "respiratory_rate": 12.0,   # breaths/min across the window
}

# ---------------------------------------------------------------------------
# Nonlinear-dynamics core (domain-agnostic math, private to this module)
# ---------------------------------------------------------------------------


def _phase_space_embedding(stream: np.ndarray, dt: float = 0.01) -> np.ndarray:
    """Augment a 1-D signal with its 1st/2nd derivatives: (value, velocity, accel)."""
    stream = np.asarray(stream, dtype=float)
    if len(stream) < 3:
        z = np.zeros_like(stream)
        return np.column_stack((stream, z, z))
    velocity = np.gradient(stream, dt)
    acceleration = np.gradient(velocity, dt)
    return np.column_stack((stream, velocity, acceleration))


def _estimate_embedding_lag_dwt(signal: np.ndarray) -> int:
    """Estimate a time-delay embedding lag from DWT detail-band zero crossings."""
    signal = np.asarray(signal, dtype=float)
    if len(signal) < 8:
        return 1
    wavelet = pywt.Wavelet("db4")
    max_level = pywt.dwt_max_level(len(signal), wavelet.dec_len)
    if max_level < 1:
        return 1
    coeffs = pywt.wavedec(signal, wavelet, level=min(2, max_level))
    detail = coeffs[1]
    zero_crossings = np.where(np.diff(np.sign(detail)))[0]
    if len(zero_crossings) < 2:
        return 2
    return max(1, int(np.mean(np.diff(zero_crossings))))


def _phase_coherence(phase_a: np.ndarray, phase_b: np.ndarray) -> np.ndarray:
    """Per-sample Kuramoto order parameter between two phase signals (0..1)."""
    combined = np.column_stack((phase_a, phase_b))
    return np.abs(np.mean(np.exp(1j * combined), axis=1))


def _largest_lyapunov_exponent(series: np.ndarray, lag: int,
                               embedding_dim: int = 3,
                               max_horizon: Optional[int] = None) -> float:
    """Rosenstein-style estimate of the largest Lyapunov exponent (per sample).

    For every embedded point we take its nearest temporally-separated
    neighbour, track how the pair separates over `max_horizon` forward steps,
    average ln(separation) across all pairs, and return the slope of that
    divergence curve.

    Positive  -> nearby trajectories diverge (less regular / higher complexity).
    ~Zero/neg -> nearby trajectories stay bounded (more regular / lower complexity).

    NB: the clinical *meaning* of the sign is condition-specific (see
    physiologic_complexity_adapter). This function only reports the dynamics.
    The value is per-sample; multiply by the true sample rate for units of 1/s.
    """
    series = np.asarray(series, dtype=float)
    n = len(series)
    if lag < 1 or n < (embedding_dim - 1) * lag + 20:
        return 0.0

    rows = n - (embedding_dim - 1) * lag
    stride = series.strides[0]
    # .copy() -> we must not hold a stride-tricked view of a local after return.
    vectors = np.lib.stride_tricks.as_strided(
        series, shape=(rows, embedding_dim), strides=(stride, lag * stride)
    ).copy()
    m = len(vectors)

    if max_horizon is None:
        max_horizon = min(20, m // 4)
    if max_horizon < 2:
        return 0.0

    tree = KDTree(vectors)
    pairs = []
    for i in range(m):
        k = min(embedding_dim + 5, m)
        _, idx = tree.query(vectors[i], k=k)
        neighbour = next((int(j) for j in np.atleast_1d(idx) if abs(int(j) - i) > lag), None)
        if neighbour is not None:
            pairs.append((i, neighbour))
    if len(pairs) < 5:
        return 0.0

    log_div = np.zeros(max_horizon)
    counts = np.zeros(max_horizon)
    for i, j in pairs:
        for k in range(max_horizon):
            if i + k < m and j + k < m:
                d = np.linalg.norm(vectors[i + k] - vectors[j + k])
                if d > 0.0:
                    log_div[k] += math.log(d)
                    counts[k] += 1.0

    valid = counts > 0
    if valid.sum() < 2:
        return 0.0
    curve = log_div[valid] / counts[valid]
    steps = np.arange(max_horizon)[valid].astype(float)
    return float(np.polyfit(steps, curve, 1)[0])   # per-sample divergence rate


# ---------------------------------------------------------------------------
# Adapters
# ---------------------------------------------------------------------------


def vitals_bounds_adapter(snapshot: dc.VitalsSnapshot,
                          reference: Optional[Dict[str, Dict[str, Tuple[float, float]]]] = None
                          ) -> dc.RiskOutput:
    """Age-aware range check on heart rate and respiratory rate.

    Age band is read from snapshot.context["age_band"] (one of the keys in
    PEDIATRIC_VITALS_REFERENCE); defaults to "adolescent" if absent. Pass
    `reference` to override the table entirely.

    *** The numeric ranges are illustrative defaults. Before any clinical use,
    replace them with your validated PEWS ranges. ***
    """
    table = reference or PEDIATRIC_VITALS_REFERENCE
    ctx = snapshot.context or {}
    band = ctx.get("age_band", "adolescent")
    ranges = table.get(band, table["adolescent"])

    hr_lo, hr_hi = ranges["hr"]
    rr_lo, rr_hi = ranges["rr"]

    def _excursion(value: float, lo: float, hi: float) -> float:
        if value < lo:
            return lo - value
        if value > hi:
            return value - hi
        return 0.0

    hr_dev = _excursion(snapshot.heart_rate, hr_lo, hr_hi)
    rr_dev = _excursion(snapshot.respiratory_rate, rr_lo, rr_hi)

    score = 0.0
    score += 5.0 if hr_dev > 0.0 else 0.0
    score += 3.0 if rr_dev > 0.0 else 0.0
    score += 2.0 if (hr_dev > 0.0 and rr_dev > 0.0) else 0.0   # both out of range -> escalate

    return dc.RiskOutput(
        adapter_name="vitals_bounds",
        metric_score=float(score),
        confidence_rating=0.95,
        meta_payload={
            "age_band": band,
            "hr": snapshot.heart_rate, "hr_range": [hr_lo, hr_hi], "hr_excursion": hr_dev,
            "rr": snapshot.respiratory_rate, "rr_range": [rr_lo, rr_hi], "rr_excursion": rr_dev,
        },
    )


def physiologic_complexity_adapter(snapshot: dc.VitalsSnapshot) -> dc.RiskOutput:
    """Heart-rate / respiratory complexity index from short vitals histories.

    Computes the phase coupling between the HR and RR trajectories and the
    largest Lyapunov exponent of that coupling.

    *** RISK-MAPPING CAVEAT -- read before trusting the score ***
    Unlike the vehicle case, "positive Lyapunov = bad" is NOT clinically
    established. In several deterioration/sepsis contexts the danger signal is
    the OPPOSITE: a LOSS of variability/complexity (overly regular dynamics),
    e.g. the physiology behind neonatal HeRO-type monitoring. The correct
    direction and threshold are condition- and age-specific and must come from
    your pilot data plus clinical evidence.

    Therefore this adapter reports the metric but defaults to metric_score=0.0
    (INFORMATIONAL / UNSCORED) until you calibrate the mapping. Set
    context["complexity_scoring"] = "enabled" only after that calibration, and
    replace the stand-in mapping below with the calibrated one.

    Expects recent histories in snapshot.context:
        context["historical_hr_stream"] : iterable[float]  (bpm)
        context["historical_rr_stream"] : iterable[float]  (breaths/min)
    """
    ctx = snapshot.context or {}
    hr_hist = np.asarray(ctx.get("historical_hr_stream", [snapshot.heart_rate]), dtype=float)
    rr_hist = np.asarray(ctx.get("historical_rr_stream", [snapshot.respiratory_rate]), dtype=float)

    if len(hr_hist) < 10 or len(rr_hist) < 10:
        return dc.RiskOutput("physiologic_complexity", 0.0, 0.50, {"status": "stabilizing"})

    n = min(len(hr_hist), len(rr_hist))
    hr_hist, rr_hist = hr_hist[-n:], rr_hist[-n:]

    lag = _estimate_embedding_lag_dwt(hr_hist)
    hr_emb = _phase_space_embedding(hr_hist)
    rr_emb = _phase_space_embedding(rr_hist)
    coherence = _phase_coherence(
        np.arctan2(hr_emb[:, 1], hr_emb[:, 0]),
        np.arctan2(rr_emb[:, 1], rr_emb[:, 0]),
    )
    lle = _largest_lyapunov_exponent(coherence, lag)

    scoring_enabled = ctx.get("complexity_scoring") == "enabled"
    score = 0.0
    if scoring_enabled:
        # STAND-IN ONLY. Direction/threshold intentionally left to calibration.
        score = float(abs(lle))

    return dc.RiskOutput(
        adapter_name="physiologic_complexity",
        metric_score=score,
        confidence_rating=0.90 if scoring_enabled else 0.50,
        meta_payload={
            "lyapunov_exponent": lle,
            "mean_hr_rr_coherence": float(np.mean(coherence)),
            "embedding_lag": lag,
            "scored": scoring_enabled,
            "note": "metric informational until clinically calibrated",
        },
    )


# ---------------------------------------------------------------------------
# Cross-domain enhancements
# ---------------------------------------------------------------------------


@dataclass
class DataQuality:
    valid_signals: Dict[str, bool]
    invalid_signals: Dict[str, str]        # name -> reason
    source_agreement: Dict[str, float]     # name -> fraction of sources agreeing
    completeness: float                    # fraction of required signals present & valid
    min_agreement: float                   # worst per-signal source agreement
    abstain: bool                          # too little trustworthy data to score


def physiological_validity_gate(
    snapshot: dc.VitalsSnapshot,
    limits: Optional[Dict[str, Tuple[float, float]]] = None,
) -> Tuple[Dict[str, bool], Dict[str, str]]:
    """Artifact pre-filter (black-hole validity gate, applied to vitals).

    Flags physiologically impossible readings so they are excluded from scoring
    rather than alarmed on. Checks heart_rate and respiratory_rate from the
    snapshot, plus spo2 / temp_c if present in snapshot.context. Returns
    (valid_signals, invalid_signals); a signal that is simply not measured is
    omitted from both (missing, not invalid).
    """
    table = limits or PHYSIOLOGIC_LIMITS
    ctx = snapshot.context or {}
    candidates: Dict[str, Optional[float]] = {
        "heart_rate": snapshot.heart_rate,
        "respiratory_rate": snapshot.respiratory_rate,
        "spo2": ctx.get("spo2"),
        "temp_c": ctx.get("temp_c"),
    }

    valid: Dict[str, bool] = {}
    invalid: Dict[str, str] = {}
    for name, value in candidates.items():
        if value is None:
            continue
        lo, hi = table.get(name, (-math.inf, math.inf))
        if not np.isfinite(value):
            valid[name], invalid[name] = False, "non-finite reading"
        elif value < lo or value > hi:
            valid[name], invalid[name] = False, f"{value} outside physiologic [{lo}, {hi}]"
        else:
            valid[name] = True
    return valid, invalid


def vote_sources(readings, tolerance: float) -> Tuple[Optional[float], float, float, bool]:
    """Majority vote across redundant sensors for one quantity
    (flight-control redundancy/voting).

    Returns (agreed_value, fraction_agreeing, dispersion, artifact_flag). The
    agreed value is the median of the cluster within `tolerance` of the overall
    median; a non-agreeing source is treated as a likely artifact.
    """
    arr = np.asarray([r for r in readings if r is not None and np.isfinite(r)], dtype=float)
    if arr.size == 0:
        return None, 0.0, 0.0, False
    if arr.size == 1:
        return float(arr[0]), 1.0, 0.0, False
    med = float(np.median(arr))
    agreeing = arr[np.abs(arr - med) <= tolerance]
    fraction = float(agreeing.size) / float(arr.size)
    dispersion = float(np.max(arr) - np.min(arr))
    agreed_value = float(np.median(agreeing)) if agreeing.size else med
    artifact = agreeing.size < arr.size
    return agreed_value, fraction, dispersion, artifact


def assess_data_quality(
    snapshot: dc.VitalsSnapshot,
    required: Tuple[str, ...] = ("heart_rate", "respiratory_rate"),
    source_tolerances: Optional[Dict[str, float]] = None,
) -> DataQuality:
    """Combine the validity gate and multi-source voting into one data-quality
    summary the fusion conditions confidence on.

    Multi-source readings, when present, are read from
    snapshot.context["<signal>_sources"] (e.g. context["heart_rate_sources"]).
    """
    tolerances = source_tolerances or {"heart_rate": 5.0, "respiratory_rate": 3.0}
    ctx = snapshot.context or {}
    valid, invalid = physiological_validity_gate(snapshot)

    agreement: Dict[str, float] = {}
    for name in required:
        sources = ctx.get(f"{name}_sources")
        if sources:
            _, fraction, _, artifact = vote_sources(sources, tolerances.get(name, 5.0))
            agreement[name] = fraction
            if artifact and valid.get(name, True):
                valid[name] = False
                invalid[name] = "redundant sources disagree"
        else:
            agreement[name] = 1.0          # single source -> no cross-check available

    present_and_valid = sum(1 for n in required if valid.get(n, False))
    completeness = present_and_valid / float(len(required)) if required else 0.0
    min_agreement = min((agreement[n] for n in required), default=1.0)
    abstain = completeness < 0.5

    return DataQuality(
        valid_signals=valid,
        invalid_signals=invalid,
        source_agreement=agreement,
        completeness=completeness,
        min_agreement=min_agreement,
        abstain=abstain,
    )


def vitals_rate_adapter(snapshot: dc.VitalsSnapshot,
                        rate_limits: Optional[Dict[str, float]] = None) -> dc.RiskOutput:
    """Rate-of-change alarm -- the power-grid ROCOF idea applied to vitals.

    A vital moving faster than its window limit is flagged even while its
    absolute value is still in the age band, because the rate of deterioration
    leads the absolute breach. Magnitude (not sign) is used: a fast bradycardic
    fall and a fast tachy climb are both flagged, with direction reported.

    Uses the same histories as the complexity adapter:
        context["historical_hr_stream"], context["historical_rr_stream"]
    If context["sample_period_s"] is given, a per-minute rate is also reported
    (informational); the alarm itself is on total change across the window,
    which needs no sampling assumption.

    *** RATE_LIMITS_PER_WINDOW are illustrative; calibrate to your window. ***
    """
    limits = rate_limits or RATE_LIMITS_PER_WINDOW
    ctx = snapshot.context or {}
    streams = {
        "heart_rate": np.asarray(ctx.get("historical_hr_stream", []), dtype=float),
        "respiratory_rate": np.asarray(ctx.get("historical_rr_stream", []), dtype=float),
    }
    period_s = ctx.get("sample_period_s")

    score = 0.0
    detail: Dict[str, Any] = {}
    any_history = False
    for name, stream in streams.items():
        if len(stream) < 3:
            detail[name] = {"status": "insufficient_history"}
            continue
        any_history = True
        x = np.arange(len(stream), dtype=float)
        slope = float(np.polyfit(x, stream, 1)[0])         # per-sample
        total_change = abs(slope) * (len(stream) - 1)      # over the window
        limit = limits.get(name, math.inf)
        exceeded = total_change > limit
        if exceeded:
            score += 5.0 if name == "heart_rate" else 3.0
        entry: Dict[str, Any] = {
            "slope_per_sample": slope,
            "total_change_over_window": total_change,
            "limit": limit,
            "exceeded": exceeded,
            "direction": "rising" if slope > 0 else "falling",
        }
        if period_s:
            entry["rate_per_min"] = slope * (60.0 / period_s)
        detail[name] = entry

    return dc.RiskOutput(
        adapter_name="vitals_rate",
        metric_score=float(score),
        confidence_rating=0.90 if any_history else 0.40,
        meta_payload=detail,
    )


def fuse_clinical_risk(outputs, quality: DataQuality,
                       weights: Optional[Dict[str, float]] = None,
                       confidence_floor: float = 0.5) -> dc.RiskOutput:
    """Confidence-conditioned fusion across adapter outputs that ABSTAINS when
    the inputs are too thin (the black-hole adapter's lesson on the 7-engine
    stack: report how much to trust the output, and decline to assert when you
    cannot).

    - Only outputs at/above `confidence_floor` may drive the alarm, so a
      low-confidence engine cannot scream the patient into a false alert.
    - Aggregation is safety-conservative: the worst TRUSTED score dominates
      (a single severe, trusted signal is not diluted by calm ones). A
      confidence-weighted mean is reported alongside for transparency.
    - Fused confidence is the mean trusted-engine confidence scaled by data
      completeness and the worst source-agreement, so missing / noisy /
      contradicted inputs visibly lower trust.
    - If data quality says abstain, or nothing clears the floor, the fusion
      returns score 0 with an ABSTAIN flag rather than a clinical figure.
    """
    w = weights or {}

    if quality.abstain:
        return dc.RiskOutput(
            adapter_name="clinical_fused",
            metric_score=0.0,
            confidence_rating=0.20,
            meta_payload={
                "abstained": True,
                "reason": "insufficient trustworthy data",
                "completeness": quality.completeness,
                "invalid_signals": quality.invalid_signals,
            },
        )

    trusted = [o for o in outputs if o.confidence_rating >= confidence_floor]
    if not trusted:
        return dc.RiskOutput(
            adapter_name="clinical_fused",
            metric_score=0.0,
            confidence_rating=0.20,
            meta_payload={"abstained": True, "reason": "no signal above confidence floor"},
        )

    fused_score = max(o.metric_score * w.get(o.adapter_name, 1.0) for o in trusted)
    wsum = sum(o.metric_score * o.confidence_rating * w.get(o.adapter_name, 1.0) for o in trusted)
    wtot = sum(o.confidence_rating * w.get(o.adapter_name, 1.0) for o in trusted)
    weighted_mean = wsum / wtot if wtot > 0 else 0.0

    mean_conf = sum(o.confidence_rating for o in trusted) / len(trusted)
    data_quality_factor = quality.completeness * quality.min_agreement
    fused_conf = float(max(0.0, min(1.0, mean_conf * data_quality_factor)))

    contributions = {
        o.adapter_name: {
            "score": o.metric_score,
            "confidence": o.confidence_rating,
            "trusted": o.confidence_rating >= confidence_floor,
        }
        for o in outputs
    }

    return dc.RiskOutput(
        adapter_name="clinical_fused",
        metric_score=float(fused_score),
        confidence_rating=fused_conf,
        meta_payload={
            "abstained": False,
            "dominant_score": fused_score,
            "confidence_weighted_mean": weighted_mean,
            "contributions": contributions,
            "completeness": quality.completeness,
            "min_source_agreement": quality.min_agreement,
            "data_quality_factor": data_quality_factor,
        },
    )
