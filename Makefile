.PHONY: install install-dev lint format typecheck test scout smoke clean

install:
	pip install -e .

install-dev:
	pip install -e ".[dev]"

lint:
	ruff check .

format:
	ruff format .

typecheck:
	mypy

test:
	pytest -v

scout:
	python -m agents.scout.main

smoke:
	python scripts/smoke_reddit_fetch.py

clean:
	rm -rf build dist *.egg-info .pytest_cache .ruff_cache .mypy_cache
	find . -type d -name __pycache__ -exec rm -rf {} +
