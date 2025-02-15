.PHONY: install run clean test lint

install:
	python -m venv venv
	. venv/bin/activate && pip install -r requirements.txt

run:
	uvicorn app.main:app --reload --port 8000

clean:
	find . -type d -name __pycache__ -exec rm -rf {}

lint:
	black .
	flake8 .

test:
	pytest

.PHONY: help

help:
	@echo "Available commands:"
	@echo " make install    - Create virtual environment and install dependencies"