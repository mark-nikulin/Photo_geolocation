SHELL := /bin/bash
.PHONY: help install dev test clean build run docker-up docker-down lint format

help:
	@echo "Available commands:"
	@echo "  install     - Install dependencies into virtual environment"
	@echo "  dev         - Run development server"
	@echo "  test        - Run tests with coverage"
	@echo "  clean       - Clean cache and temporary files"
	@echo "  build       - Build Docker image"
	@echo "  run         - Run with Docker Compose"
	@echo "  docker-up   - Start all services"
	@echo "  docker-down - Stop all services"
	@echo "  lint        - Run linting (flake8, mypy)"
	@echo "  format      - Format code (black, isort)"

install:
	python3 -m venv .venv
	.venv/bin/pip install --upgrade pip
	.venv/bin/pip install -e . || .venv/bin/pip install -r requirements.txt || .venv/bin/pip install fastapi uvicorn pydantic sqlalchemy alembic asyncpg redis pillow google-generativeai geopy httpx aiofiles python-multipart python-jose passlib celery prometheus-client structlog pydantic-settings aiosqlite pytest pytest-asyncio pytest-cov black isort flake8 mypy pre-commit
	.venv/bin/pre-commit install || true

dev:
	.venv/bin/python -m app.main

test:
	.venv/bin/pytest tests/ -v

clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	rm -rf htmlcov/
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf uploads/*.jpg uploads/*.png
	rm -rf *.db

build:
	docker build -t photo-geolocation .

run: build
	docker-compose up

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down -v

lint:
	.venv/bin/flake8 app/ tests/
	.venv/bin/mypy app/

format:
	.venv/bin/black app/ tests/
	.venv/bin/isort app/ tests/

setup-dev: install
	cp -n .env.example .env || true
	@echo "Please edit .env file with your API keys"

migrate:
	.venv/bin/alembic upgrade head
