# TaxPilot AI Backend

Backend foundation for TaxPilot AI, implemented as a modular monolith prepared for future service extraction.

This pack initializes only the platform foundation: FastAPI, configuration, SQLAlchemy, Alembic, PostgreSQL, Redis, structured logging, global exception handling, Docker, and a health endpoint.

## Requirements

- Python 3.12
- uv
- Docker and Docker Compose

## Setup

Copy the example environment file:

```bash
cp .env.example .env
```

Install dependencies:

```bash
uv sync
```

## Run Locally

Start PostgreSQL and Redis, then run:

```bash
uv run uvicorn app.main:app --reload
```

The API will be available at:

- API: http://localhost:8000
- Swagger UI: http://localhost:8000/docs
- Health: http://localhost:8000/api/v1/health

Expected health response:

```json
{
  "success": true,
  "message": "TaxPilot API is healthy",
  "data": {
    "status": "UP",
    "version": "1.0.0",
    "environment": "development"
  }
}
```

## Run With Docker

From the `backend` directory:

```bash
docker compose up --build
```

The stack includes:

- FastAPI backend
- PostgreSQL 16
- Redis 7

## Alembic

Create a migration:

```bash
uv run alembic revision --autogenerate -m "migration message"
```

Apply migrations:

```bash
uv run alembic upgrade head
```

Check the current migration:

```bash
uv run alembic current
```

No domain tables are included in this engineering pack.

## Quality Checks

```bash
uv run ruff check .
uv run mypy .
uv run pytest
```
