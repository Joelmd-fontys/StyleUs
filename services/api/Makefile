PYTHON ?= python3
VENV ?= .venv
MESSAGE ?= update

.PHONY: setup run migrate upgrade lint typecheck test seed reset-seed

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
