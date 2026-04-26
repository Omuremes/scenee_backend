.PHONY: help install run test clean docker-up docker-down migrate

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-15s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: ## Install Python dependencies
	pip install -r requirements.txt

run: ## Run the FastAPI application
	uvicorn app.main:app --reload

test: ## Run tests
	pytest

clean: ## Clean up cache files
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete

docker-up: ## Start Docker services
	docker-compose up -d

docker-down: ## Stop Docker services
	docker-compose down

migrate: ## Run database migrations
	alembic upgrade head

create-migration: ## Create a new migration
	alembic revision --autogenerate -m "$(msg)"

lint: ## Run code linting (if black/flake8 installed)
	@echo "Linting not configured yet"

format: ## Format code (if black installed)
	@echo "Formatting not configured yet"