# Backend Rules

- All SQLAlchemy queries go in `services/` — never in route handlers
- Use explicit columns in every SELECT — no `SELECT *`
- All money columns are `NUMERIC(12,2)` — never float
- Celery tasks must be idempotent
- ML model loaded once at startup via `lru_cache` in `scoring_service.py`
- Run `black` and `ruff` before committing
- Test DB: `pathfinder_test` — separate from dev DB
