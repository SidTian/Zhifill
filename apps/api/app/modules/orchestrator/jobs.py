"""Job state machine placeholder (SQLite in implementation phase)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class JobRecord:
    id: str
    kind: str
    status: str
    payload: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)


class InMemoryJobStore:
    """Phase 0 placeholder — replace with SQLite."""

    def __init__(self) -> None:
        self._jobs: dict[str, JobRecord] = {}

    def create(self, kind: str, payload: dict[str, Any] | None = None) -> JobRecord:
        job = JobRecord(id=str(uuid4()), kind=kind, status="pending", payload=payload or {})
        self._jobs[job.id] = job
        return job

    def get(self, job_id: str) -> JobRecord | None:
        return self._jobs.get(job_id)

    def list(self, kind: str | None = None) -> list[JobRecord]:
        jobs = list(self._jobs.values())
        if kind:
            jobs = [j for j in jobs if j.kind == kind]
        return sorted(jobs, key=lambda j: j.created_at, reverse=True)

    def update(self, job_id: str, **kwargs: Any) -> JobRecord | None:
        job = self._jobs.get(job_id)
        if not job:
            return None
        for k, v in kwargs.items():
            if hasattr(job, k):
                setattr(job, k, v)
        job.updated_at = _now()
        return job


job_store = InMemoryJobStore()
