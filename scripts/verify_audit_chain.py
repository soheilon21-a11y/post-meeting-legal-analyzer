"""Recompute and verify the audit_events hash chain against the database.

Usage:
    python scripts/verify_audit_chain.py

Exits 0 when every chained row links to its predecessor (prev_hash matches
the previous row_hash, seq is gap-free) and its stored row_hash equals
sha256(prev_hash + canonical JSON of the row).  Rows written before the
chain migration (NULL seq/row_hash) are reported as legacy and skipped —
tampering can only be detected within chained segments.  Exits 1 on any
integrity problem.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.db.models.audit import AuditEvent  # noqa: E402
from app.infrastructure.persistence.audit_chain import verify_audit_chain  # noqa: E402


async def _run() -> int:
    engine = create_async_engine(get_settings().postgres.database_url, echo=False)
    try:
        async with AsyncSession(engine) as db:
            result = await db.execute(
                select(AuditEvent).order_by(AuditEvent.seq.nulls_first())
            )
            events = list(result.scalars().all())
    finally:
        await engine.dispose()

    chained = [event for event in events if event.seq is not None]
    legacy = len(events) - len(chained)

    problems = verify_audit_chain(events)
    if problems:
        print(f"AUDIT CHAIN BROKEN: {len(problems)} problem(s) "
              f"in {len(events)} event(s), {legacy} legacy row(s) outside the chain")
        for problem in problems:
            print(f"  - {problem}")
        return 1

    print(
        f"AUDIT CHAIN OK: {len(chained)} chained event(s) verified, "
        f"{legacy} legacy row(s) skipped"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_run()))
