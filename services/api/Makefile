VENV ?= .venv
MESSAGE ?= update
COMPOSE_FILE := $(CURDIR)/docker-compose.yml

ifeq ($(wildcard $(VENV)/bin/python),)
PYTHON ?= python3
else
PYTHON ?= $(VENV)/bin/python
endif

.PHONY: setup run worker worker-service migrate upgrade lint typecheck test benchmark-category review-feedback-report review-feedback-export seed reset-seed db-up db-down

setup:
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -e .[dev]

run:
	$(PYTHON) -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

worker:
	$(PYTHON) -m app.worker

worker-service:
	$(PYTHON) -m uvicorn app.worker_service:app --host 0.0.0.0 --port 8001

migrate:
	$(PYTHON) -m alembic revision --autogenerate -m "$(MESSAGE)"

upgrade:
	$(PYTHON) -m alembic upgrade head

lint:
	$(PYTHON) -m ruff check .

typecheck:
	$(PYTHON) -m mypy app

test:
	$(PYTHON) -m pytest -q

benchmark-category:
	STYLEUS_RUN_CATEGORY_BENCH=1 $(PYTHON) -m app.ai.benchmark --strategies heuristic pipeline full focus

review-feedback-report:
	$(PYTHON) -m app.ai.feedback_eval --manifest tests/fixtures/upload_review_feedback_cases.yaml

review-feedback-export:
	$(PYTHON) -m app.ai.feedback_eval --output-dir media/review_feedback_eval

seed:
	$(PYTHON) -m app.seed.runner

reset-seed:
	$(PYTHON) -m app.seed.runner --reset

db-up:
	docker compose -f $(COMPOSE_FILE) up -d

db-down:
	docker compose -f $(COMPOSE_FILE) down
