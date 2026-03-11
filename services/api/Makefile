VENV ?= .venv
MESSAGE ?= update
COMPOSE_FILE := $(CURDIR)/docker-compose.yml

ifeq ($(wildcard $(VENV)/bin/python),)
PYTHON ?= python3
else
PYTHON ?= $(VENV)/bin/python
endif

.PHONY: setup run worker migrate upgrade lint typecheck test seed reset-seed db-up db-down

setup:
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -e .[dev]

run:
	$(PYTHON) -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

worker:
	$(PYTHON) -m app.worker

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

seed:
	$(PYTHON) -m app.seed.runner

reset-seed:
	$(PYTHON) -m app.seed.runner --reset

db-up:
	docker compose -f $(COMPOSE_FILE) up -d

db-down:
	docker compose -f $(COMPOSE_FILE) down
