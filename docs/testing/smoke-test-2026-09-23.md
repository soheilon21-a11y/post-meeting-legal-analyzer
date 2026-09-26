# Smoke Test — 2026-09-23 (manual, staging on dev machine)

Redacted copy of the local smoke-test log; identifiers anonymized.

## Result: PASS with findings

Update: F-1, F-2, F-3 fixed — see commit history.
Note: F-1–F-14 are issues; F-15–F-17 are positive verifications (what worked during the same run).

Both flows (analyze+RAG, redline+HITL) completed end-to-end locally.
All findings below are logged for follow-up.

## Environment
Docker: postgres/qdrant/redis/minio — qdrant container "unhealthy" (see F-1)
Runtime: uvicorn, Windows, CPU-only Ollama (llama3, nomic-embed-text)

## Findings
- F-1 (bug, quick): lifecycle probe calls /health → 404; Qdrant is healthy (/readyz returns 200). Fix: manager.py → use /readyz. Same class of bug as the docker healthcheck fixed 2 weeks ago.
- F-2 (bug, quick): analysis PDF footer renders em-dash as "â€"" (encoding). Note: redline PDF renders em-dash correctly — issue is localized to the analysis report template.
- F-3 (bug, quick): analysis PDF header "Status: completed" vs footer "ready_for_review" — inconsistent labels.
- F-4 (model): fabricated year "2022-10-15" for a date with no year in source. Appears in the client-facing PDF → P1. Fix via prompt instruction: unknown year → null or current year; never invent.
- F-5 (model): citation quote unrelated to its finding's claim (finding #2).
- F-6 (model): duplicate near-identical proposals (3x) from one generate run.
- F-7 (design): re-running /generate adds duplicate changes instead of replacing pending ones (no idempotency).
- F-8 (design): /analyze with a non-existent matter silently proceeds with no corpus grounding. Dangerous for a legal tool: lawyer assumes contract comparison happened. Should 404 or warn.
- F-9 (claim gap): "flags discrepancies" — no explicit discrepancy flag in API response or PDF; contrast exists only implicitly (two opposing findings + summary). Either add a Discrepancies section or soften website wording.
- F-10 (claim gap): redline citations use source_id "CONTEXT 2", not real document IDs — contradicts "validated against real document IDs" claim.
- F-11 (quality): review comments not rendered in redline PDF report.
- F-12 (cosmetic): redline PDF: "string (original-clause.txt.txt)" in Source document column — type placeholder leaked into render.
- F-13 (cosmetic): redline PDF: "medium" wraps to "mediu m"; header columns overlap.
- F-14 (perf): ~126–137s analyze on CPU (llama3); 46–84s redline generate. For demo video: warm-up run before recording.
- F-15 (positive): analysis PDF distinguishes transcript vs corpus citations in footnotes — core claim verified.
- F-16 (positive): HITL gate works: approve/reject + comments persisted.
- F-17 (positive): 422 validation errors are precise and leak nothing.

## Evidence
- analysis_id: <id> (PDF saved)
- redline_id: <id> (PDF saved)
- matter: <id> (<demo-account>)