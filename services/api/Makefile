PYTHON ?= python3
VENV ?= .venv
MESSAGE ?= update
COMPOSE_FILE := $(CURDIR)/docker-compose.yml

.PHONY: setup run migrate upgrade lint typecheck test seed reset-seed db-up db-down

setup:
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -e .[dev]

run:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

migrate:
	alembic revision --autogenerate -m "$(MESSAGE)"

upgrade:
	alembic upgrade head

lint:
	ruff check .

typecheck:
	mypy app

test:
	pytest -q

seed:
	$(PYTHON) -m app.seed.runner

reset-seed:
	$(PYTHON) -m app.seed.runner --reset

db-up:
	docker compose -f $(COMPOSE_FILE) up -d

db-down:
	docker compose -f $(COMPOSE_FILE) down
