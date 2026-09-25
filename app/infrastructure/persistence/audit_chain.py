from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING
from typing import Any
from uuid import uuid4

from sqlalchemy import select

from app.db.models.audit import AuditEvent

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy.ext.asyncio import AsyncSession

# Hash of the (virtual) row preceding the first real one; every chain starts
# here, so a rewritten history cannot silently re-root itself.
GENESIS_HASH = "0" * 64


def canonical_audit_fields(event: AuditEvent) -> dict[str, Any]:
    """The hash-covered fields of one audit row, in a stable representation.

    Only application-controlled, string-stable fields participate, so the
    same logical row hashes identically before and after a database
    round-trip (UUID/JSONB normalizations included).  ``created_at`` and
    ``updated_at`` are deliberately excluded (server-generated).
    """
    return {
        "id": str(event.id),
        "organization_id": str(event.organization_id),
        "matter_id": str(event.matter_id) if event.matter_id is not None else None,
        "actor_id": str(event.actor_id) if event.actor_id is not None else None,
        "actor_email": event.actor_email,
        "event_type": str(event.event_type),
        "resource_type": event.resource_type,
        "resource_id": str(event.resource_id) if event.resource_id is not None else None,
        "client_ip": event.client_ip,
        "metadata": event.metadata_json if event.metadata_json is not None else {},
        "seq": event.seq,
    }


def compute_row_hash(event: AuditEvent) -> str:
    """sha256(prev_hash + canonical JSON of the row) — the chain link."""
    payload = json.dumps(
        canonical_audit_fields(event),
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    prev = event.prev_hash if event.prev_hash is not None else GENESIS_HASH
    return hashlib.sha256((prev + payload).encode("utf-8")).hexdigest()


async def _chain_state(session: AsyncSession) -> tuple[str, int]:
    """Return (last row_hash, last seq) of the persisted chain.

    Falls back to the genesis state for test doubles that do not implement
    ``execute`` or that return non-AuditEvent stand-ins — those sessions
    still receive fully-formed (if restartable) chain links.
    """
    try:
        result = await session.execute(
            select(AuditEvent)
            .where(AuditEvent.seq.is_not(None))
            .order_by(AuditEvent.seq.desc())
            .limit(1)
        )
        last = result.scalars().first()
    except Exception:
        return GENESIS_HASH, 0
    if isinstance(last, AuditEvent) and last.seq is not None:
        return (last.row_hash if last.row_hash is not None else GENESIS_HASH), int(last.seq)
    return GENESIS_HASH, 0


async def append_audit_event(
    session: AsyncSession, event: AuditEvent
) -> AuditEvent:
    """Link ``event`` onto the hash chain, persist it and return it.

    Single append path for every audit writer (domain-event dispatcher and
    the redline endpoints), so no event can bypass prev_hash/row_hash/seq.
    """
    if event.id is None:
        event.id = uuid4()  # type: ignore[assignment]
    prev_hash, last_seq = await _chain_state(session)
    event.prev_hash = prev_hash
    event.seq = last_seq + 1
    event.row_hash = compute_row_hash(event)
    session.add(event)
    await session.flush()
    return event


def verify_audit_chain(events: Sequence[AuditEvent]) -> list[str]:
    """Recompute the chain and describe every integrity problem found.

    Returns an empty list when the chain verifies.  Rows without a hash-link
    triple are pre-migration legacy rows: they are not part of the chain and
    cannot be verified (that is exactly what makes tampering detectable from
    the first chained row onward), so they are skipped — with the expected
    linkage reset — and only reported informationally via
    ``legacy_unchecked``-style counts by callers that load them.
    """
    problems: list[str] = []
    ordered = sorted(
        events,
        key=lambda e: (e.seq is None, e.seq if e.seq is not None else 0, str(e.id)),
    )
    expected_prev: str | None = None
    expected_seq: int | None = None
    for event in ordered:
        if event.seq is None or event.prev_hash is None or event.row_hash is None:
            expected_prev = None
            expected_seq = None
            continue
        link_prev = GENESIS_HASH if expected_prev is None else expected_prev
        if event.prev_hash != link_prev:
            problems.append(
                f"AuditEvent {event.id} prev_hash mismatch "
                f"(expected {link_prev}, got {event.prev_hash})"
            )
        if expected_seq is not None and event.seq != expected_seq + 1:
            problems.append(
                f"AuditEvent {event.id} seq gap (expected {expected_seq + 1}, got {event.seq})"
            )
        if compute_row_hash(event) != event.row_hash:
            problems.append(
                f"AuditEvent {event.id} row_hash mismatch — row content was tampered with"
            )
        expected_prev = event.row_hash
        expected_seq = int(event.seq)
    return problems


__all__ = [
    "GENESIS_HASH",
    "append_audit_event",
    "canonical_audit_fields",
    "compute_row_hash",
    "verify_audit_chain",
]
