"""
Async Scheduler
===============

Main orchestrator for async job scheduling.
Handles: queueing → provisional verdict → worker execution → reconciliation.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Callable, Dict, Optional

from job_queue import JobQueue, JobStatus, ScheduledJob
from worker import WorkerPool
from provisional_store import ProvisionalStore

logger = logging.getLogger("OBSERVE_SCHEDULER")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(
        "[OBSERVE_SCHEDULER] %(asctime)s %(levelname)s %(message)s"
    ))
    logger.addHandler(handler)


# ============================================================
# ASYNC SCHEDULER
# ============================================================

class AsyncScheduler:
    """Orchestrates async heavy engine execution with provisional verdicts."""

    def __init__(
        self,
        num_workers: int = 2,
        heavy_engines: list = None,
    ):
        self.num_workers = num_workers
        self.heavy_engines = heavy_engines or ["bayesian_fusion"]
        self.job_queue = JobQueue()
        self.provisional_store = ProvisionalStore()
        self.worker_pool: Optional[WorkerPool] = None
        self.is_running = False

    async def start(self) -> None:
        """Start the scheduler and worker pool."""
        logger.info("Starting AsyncScheduler")

        # Initialize worker pool with mock executor for now
        self.worker_pool = WorkerPool(
            num_workers=self.num_workers,
            job_queue=self.job_queue,
            engine_executor=self._execute_engine,
            provisional_store=self.provisional_store,
        )

        await self.worker_pool.start()
        self.is_running = True

    async def stop(self) -> None:
        """Stop the scheduler and worker pool."""
        logger.info("Stopping AsyncScheduler")
        self.is_running = False

        if self.worker_pool:
            await self.worker_pool.stop()

    async def schedule_heavy_job(
        self,
        patient_id: str,
        engine_name: str,
        vitals_snapshot: Dict,
        fast_provisional_fn: Callable,
    ) -> Dict:
        """
        Schedule a heavy job and return provisional verdict immediately.

        Flow:
        1. Call fast_provisional_fn for quick verdict
        2. Queue job for heavy execution
        3. Return provisional verdict immediately (don't wait)
        4. Worker processes job in background
        5. Reconcile provisional with final result
        """

        logger.info(f"Scheduling heavy job: patient={patient_id}, engine={engine_name}")

        # 1. Generate provisional verdict immediately (fast)
        provisional = await fast_provisional_fn(vitals_snapshot)

        # 2. Create job
        job = ScheduledJob(
            patient_id=patient_id,
            engine_name=engine_name,
            vitals_snapshot=vitals_snapshot,
        )

        # 3. Queue job for background execution
        job_id = await self.job_queue.enqueue(job)

        # 4. Store provisional verdict
        self.provisional_store.store_provisional(
            patient_id=patient_id,
            job_id=job_id,
            risk_score=provisional.get("risk_score", 0.0),
            confidence=provisional.get("confidence", 0.0),
            regime=provisional.get("regime", "stable"),
        )

        # 5. Return provisional verdict immediately (don't block)
        return {
            "is_provisional": True,
            "job_id": job_id,
            "risk_score": provisional.get("risk_score"),
            "confidence": provisional.get("confidence"),
            "regime": provisional.get("regime"),
            "rationale": "Provisional verdict (heavy job running in background)",
            "provisional_timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def get_job_status(self, job_id: str) -> Optional[Dict]:
        """Get status and current result of a job."""
        status = self.job_queue.get_job_status(job_id)

        if status is None:
            return None

        job = self.job_queue.jobs.get(job_id)

        return {
            "job_id": job_id,
            "status": status.value,
            "created_at": job.created_at.isoformat(),
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "final_result": job.final_result,
            "error": job.error,
            "retry_count": job.retry_count,
        }

    async def wait_for_final_result(
        self,
        job_id: str,
        timeout: float = 30.0,
    ) -> Optional[Dict]:
        """
        Wait for a job to complete (blocking with timeout).
        Use this if you want to block for final result.
        """
        start_time = datetime.now(timezone.utc)

        while True:
            elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()

            if elapsed > timeout:
                logger.warning(f"Timeout waiting for job {job_id}")
                return None

            status = self.job_queue.get_job_status(job_id)

            if status == JobStatus.COMPLETED:
                job = self.job_queue.jobs.get(job_id)
                return job.final_result

            elif status == JobStatus.FAILED:
                job = self.job_queue.jobs.get(job_id)
                logger.error(f"Job {job_id} failed: {job.error}")
                return None

            # Wait before checking again
            await asyncio.sleep(0.5)

    async def _execute_engine(self, engine_name: str, vitals: Dict) -> Dict:
        """
        Mock executor for heavy engine (to be replaced with real engine).
        In production, this would call the actual Bayesian Fusion engine.
        """
        logger.info(f"Executing heavy engine: {engine_name}")

        # Simulate heavy computation
        await asyncio.sleep(2.0)

        # Return mock result
        return {
            "engine_name": engine_name,
            "risk_score": 0.65,
            "confidence": 0.88,
            "regime": "warning",
            "triggered_rules": ["O2_TRAJECTORY: Dropping"],
        }

    def export_scheduler_state(self) -> Dict:
        """Export complete scheduler state for audit."""
        return {
            "is_running": self.is_running,
            "num_workers": self.num_workers,
            "heavy_engines": self.heavy_engines,
            "jobs": self.job_queue.export_jobs(),
            "provisionals": self.provisional_store.export_all(),
            "worker_stats": self.worker_pool.get_stats() if self.worker_pool else None,
        }


# ============================================================
# DEMO
# ============================================================

async def demo():
    """Demonstrate async scheduling."""
    scheduler = AsyncScheduler(num_workers=2)
    await scheduler.start()

    async def fast_provisional(vitals: Dict) -> Dict:
        """Fast heuristic-based provisional verdict."""
        return {
            "risk_score": 0.55,
            "confidence": 0.80,
            "regime": "caution",
        }

    # Schedule a heavy job
    provisional = await scheduler.schedule_heavy_job(
        patient_id="P001",
        engine_name="bayesian_fusion",
        vitals_snapshot={"heart_rate": 155, "oxygen_saturation": 85.0},
        fast_provisional_fn=fast_provisional,
    )

    print(f"Provisional verdict: {provisional}")
    print(f"Job ID: {provisional['job_id']}")

    # Wait for final result
    final = await scheduler.wait_for_final_result(provisional["job_id"], timeout=10.0)
    print(f"Final result: {final}")

    await scheduler.stop()


if __name__ == "__main__":
    asyncio.run(demo())
