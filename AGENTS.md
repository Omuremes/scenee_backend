# AI Agent Guidance for scenee_backend

## What this project is
- CineScope: Production-ready backend API for Android movie/events app.
- FastAPI + PostgreSQL + Firebase Auth + MinIO + Redis.
- Clean architecture: routers/services/repositories/models/schemas/core.
- Commercial-grade: async, pagination, validation, error handling, Docker support.

## Important conventions
- Async-first: All DB operations use async SQLAlchemy sessions.
- Firebase service account: Never edit `scenee-9fba8-firebase-adminsdk-fbsvc-8d3ea4e679.json`.
- Pydantic v1.10.13: Use BaseModel for schemas, Config with from_attributes=True.
- PostgreSQL: Use UUID primary keys, proper foreign keys, indexes.
- No dependency manifest: Ask user before adding packages.
- Rate limiting, logging, input validation required.

## Editing guidance
- Follow clean architecture: Business logic in services, data access in repositories.
- New endpoints: Add to `app/routers/`, register in `app/main.py`.
- Tests: Add to `tests/` with pytest-asyncio.
- Search imports before assuming frameworks.
- Prefer explicit changes; avoid broad rewrites.

## What AI should do first
- Check `README.md` for setup instructions.
- Inspect `app/core/config.py` for settings.
- Confirm dependencies/runtime with user.
- Review existing models/schemas before adding.

## Why this file is useful
- Guides AI to maintain commercial standards.
- Prevents unsafe changes to sensitive files.
- Documents complex architecture for productivity.
- Signals production-ready backend, not tutorial.
