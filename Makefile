.PHONY: demo reset booth test install seed

install:
	pip install -e ".[dev]"

seed:
	@python -m backend.memory.seed

demo:
	@echo "Starting EDRA Lounge on :8000 (orchestrator loops run inside the FastAPI process)"
	@python -m uvicorn backend.app:api --reload --host 0.0.0.0 --port 8000

reset:
	@echo "Resetting SQLite DB and re-seeding"
	@rm -f edra_lounge.db
	@python -m backend.memory.seed

booth:
	@echo "Booth mode — full-screen, offline, deterministic"
	@python -m uvicorn backend.app:api --host 0.0.0.0 --port 8000

test:
	@pytest tests/ -v
