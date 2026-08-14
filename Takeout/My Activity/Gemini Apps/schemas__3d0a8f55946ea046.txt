"""
schemas.py
----------

Iceberg API request/response schemas.

Fixed 2026-07-01: this file previously contained a byte-for-byte duplicate of
Engines/staffing_rl.py -- SimulateRequest, which API/server.py imports and
depends on, was defined nowhere in the entire repository. Not an import-path
bug; the actual content never existed. Fields below are inferred purely from
how server.py consumes the object (req.caller_id, req.intent, req.emotion,
req.steps) -- not a design decision, a direct read of the only consumer.
"""

from __future__ import annotations
from pydantic import BaseModel


class SimulateRequest(BaseModel):
    caller_id: str
    intent: str
    emotion: str = "NEUTRAL"
    steps: int
