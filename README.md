# VM Management Service

Minimal production-ready FastAPI project for VM lifecycle management.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

OpenAPI docs are available at `http://127.0.0.1:8000/docs`.

## Structure

```text
app/
  api/            # HTTP routes and dependency wiring
  core/           # settings, exception types, error handlers
  models/         # Pydantic request/response/domain models
  repositories/   # persistence boundary
  services/       # business logic
```

The default repository is in-memory so the service can run immediately. Replace
`InMemoryVMRepository` with a database-backed implementation behind the same
repository protocol for production persistence.

