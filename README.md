# Post-Meeting Legal Analyzer

Privacy-first LegalTech platform for analyzing legal meeting outputs using local AI.

## Architecture

- **Privacy-first**: 100% local AI inference — no cloud AI APIs
- **Modular monolith**: Clean Architecture with domain boundaries
- **RAG pipeline**: Hybrid retrieval with Qdrant, structure-aware chunking, local embeddings
- **AI-assisted redlining**: Human-in-the-loop clause comparison with evidence citations
- **Production-ready**: FastAPI, PostgreSQL, Docker, comprehensive testing

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
ollama pull llama3.2
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
