.PHONY: demo reset booth test install seed health

PORT ?= 8000
HOST ?= 127.0.0.1
URL  ?= http://$(HOST):$(PORT)/

install:
	pip install -e ".[dev]"

seed:
	@python -m backend.seed

# Reset DB and re-seed in a single fast pass — TASK.md acceptance: <5s.
reset:
	@echo "→ resetting SQLite DB and re-seeding"
	@rm -f edra_lounge.db edra_lounge.db-shm edra_lounge.db-wal
	@python -m backend.seed
	@echo "✓ reset complete"

# Dev mode — auto-reload, listens on all interfaces so the booth can pull from
# a tablet on the same Wi-Fi if the kiosk laptop dies during a demo.
# Defaults to live(mock) source per backend/config.py — set `LIVE_MODE=false`
# in .env (or env) to switch to synthetic auto-play.
demo:
	@echo "→ EDRA Lounge starting on $(URL) (auto-reload on)"
	@python -m uvicorn backend.app:api --reload --host 0.0.0.0 --port $(PORT)

# Booth mode — strict run for the live booth event.
#   1. reset DB so the run starts from a clean seeded state
#   2. start uvicorn in the background, wait for /health
#   3. open kiosk Chrome at the demo URL (no reload, no devtools)
# Profile source defaults to live LinkedIn (mock-key sentinel returns a
# hand-crafted author profile when no real RAPIDAPI_KEY is provided).
# Falls back to a friendly hint if `start` (Windows-only) isn't available.
booth: reset
	@echo "→ booth mode — full-screen, offline, deterministic"
	@python -m uvicorn backend.app:api --host $(HOST) --port $(PORT) & \
	  UVICORN_PID=$$!; \
	  for i in 1 2 3 4 5 6 7 8 9 10; do \
	    sleep 0.5; \
	    curl -fsS $(URL)health >/dev/null 2>&1 && break; \
	  done; \
	  echo "✓ orchestrator up at $(URL)"; \
	  ( command -v start >/dev/null 2>&1 && start chrome --kiosk $(URL) ) \
	    || ( command -v cmd.exe >/dev/null 2>&1 && cmd.exe /c start chrome --kiosk $(URL) ) \
	    || echo "open $(URL) in a kiosk-mode browser to start the demo"; \
	  wait $$UVICORN_PID

health:
	@curl -fsS $(URL)health

test:
	@pytest tests/ -v
