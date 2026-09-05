# Post-Meeting Legal Analyzer

Privacy-first LegalTech platform for analyzing legal meeting outputs using local AI.

## Architecture

- **Privacy-first**: 100% local AI inference — no cloud AI APIs
- **Modular monolith**: Clean Architecture with domain boundaries
- **RAG pipeline**: Qdrant vector retrieval with structure-aware chunking and local Ollama embeddings
- **AI-assisted redlining**: Human-in-the-loop clause comparison with evidence citations
- **Production-ready**: FastAPI, PostgreSQL, Docker, comprehensive testing
- **Traceability & auditability: audit event system with request IDs and timing middleware
- **Compliance: domain invariant validation and explicit state transitions

## Quick Start

### Prerequisites

- Python 3.12+
- Docker and Docker Compose
- [Ollama](https://ollama.ai) (for local LLM inference)

### Setup

```bash
# Clone the repository
git clone https://github.com/soheilon21-a11y/post-meeting-legal-analyzer.git
cd post-meeting-legal-analyzer

# Copy environment configuration
cp .env.example .env

# Start infrastructure services
docker compose up -d postgres qdrant redis minio

# Pull required Ollama models
ollama pull llama3
ollama pull nomic-embed-text

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

# Install dependencies
pip install -e ".[dev]"

# Run database migrations
alembic upgrade head

# Start the API server
uvicorn app.main:create_app --factory --reload --host 0.0.0.0 --port 8000
```

### Full Docker Deployment

```bash
docker compose up -d
```

The API will be available at `http://localhost:8000`.

API documentation at `http://localhost:8000/docs`.

### Retrieval-Augmented Analysis (RAG)

Index document text into a matter's local corpus, then analyze a meeting
transcript grounded against that corpus. Embeddings are generated locally
with Ollama (`nomic-embed-text`); vectors are stored in Qdrant (server mode,
or embedded mode by setting `QDRANT_LOCAL_PATH` to a writable directory such
as `data/qdrant` when no Qdrant server is available).

```bash
# Index document text under a matter
curl -X POST http://localhost:8000/api/v1/corpus/documents \
  -H "Content-Type: application/json" \
  -d '{"matter_id": "matter-1", "source_id": "contract-1", "text": "The supplier shall be liable for all direct damages."}'

# Analyze a transcript grounded against the matter's corpus
curl -X POST http://localhost:8000/api/v1/analyze \
  -H "Content-Type: application/json" \
  -d '{"text": "We discussed the supplier liability clause.", "use_llm": true, "matter_id": "matter-1"}'
```

Without `matter_id`, `/analyze` runs without corpus retrieval. If the
embedding model or vector index is unavailable, retrieval degrades to empty
evidence and the analysis still completes.

## Development

```bash
# Install pre-commit hooks
pre-commit install

# Run all checks
ruff check .
ruff format --check .
black --check .
mypy app/

# Run tests
pytest

# Run tests with coverage
pytest --cov=app --cov-report=term-missing
```

## License

MIT
