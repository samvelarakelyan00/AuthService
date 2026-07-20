# .PHONY: help up up-tests up-unit up-integration up-component up-dev \
#         down logs clean test-all test-unit test-integration test-component \
#         test-with-docker test-with-docker-unit test-with-docker-integration test-with-docker-component

DOCKER_COMPOSE = docker compose
DOCKER_COMPOSE_TEST = $(DOCKER_COMPOSE) --profile tests

# Colors for output
GREEN := \033[0;32m
RED := \033[0;31m
YELLOW := \033[0;33m
RESET := \033[0m

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  $(GREEN)%-30s$(RESET) %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ''
	@echo 'Environment variables:'
	@echo '  $(YELLOW)RUN_TESTS$(RESET)     - Set to true to run tests on startup (default: false)'
	@echo '  $(YELLOW)TEST_TYPE$(RESET)     - all, unit, integration, end2end (default: all)'
	@echo '  $(YELLOW)FAIL_ON_TEST_FAILURE$(RESET) - true/false (default: false)'

up: ## Start containers without tests
	$(DOCKER_COMPOSE) up --build

up-tests: ## Start containers with all tests
	RUN_TESTS=true TEST_TYPE=all $(DOCKER_COMPOSE) up --build

up-unit: ## Start containers with unit tests only
	RUN_TESTS=true TEST_TYPE=unit $(DOCKER_COMPOSE) up --build

up-integration: ## Start containers with integration tests only
	RUN_TESTS=true TEST_TYPE=integration $(DOCKER_COMPOSE) up --build

up-end2end: ## Start containers with end to end tests only
	RUN_TESTS=true TEST_TYPE=component $(DOCKER_COMPOSE) up --build

up-component: ## Start containers with end to end tests only
	RUN_TESTS=true TEST_TYPE=end2end $(DOCKER_COMPOSE) up --build

up-dev: ## Start containers with tests and show output (not detached)
	RUN_TESTS=true FAIL_ON_TEST_FAILURE=false $(DOCKER_COMPOSE) up --build

down: ## Stop and remove containers
	$(DOCKER_COMPOSE) down

logs: ## Show app logs
	$(DOCKER_COMPOSE) logs -f app

logs-redis: ## Show redis logs
	$(DOCKER_COMPOSE) logs -f redis

clean: ## Stop containers and remove volumes
	$(DOCKER_COMPOSE) down -v

rebuild: ## Rebuild and start containers
	$(DOCKER_COMPOSE) up --build

test-all: ## Run all tests locally (requires running containers)
	$(DOCKER_COMPOSE) exec app sh -c "cd /AuthService && uv run --python /AuthService/app/.venv/bin/python pytest tests/ -v --tb=short"

test-unit: ## Run unit tests locally
	$(DOCKER_COMPOSE) exec app sh -c "cd /AuthService && uv run --python /AuthService/app/.venv/bin/python pytest tests/unit/ -v --tb=short"

test-integration: ## Run integration tests locally
	$(DOCKER_COMPOSE) exec app sh -c "cd /AuthService && uv run --python /AuthService/app/.venv/bin/python pytest tests/integration/ -v --tb=short"

test-end2end: ## Run end2end tests locally
	$(DOCKER_COMPOSE) exec app sh -c "cd /AuthService && uv run --python /AuthService/app/.venv/bin/python pytest tests/end2end-abuse/ -v --tb=short"

test-component: ## Run component tests locally
	$(DOCKER_COMPOSE) exec app sh -c "cd /AuthService && uv run --python /AuthService/app/.venv/bin/python pytest tests/component/ -v --tb=short"

test-with-docker: ## Run all tests in isolated Docker container
	RUN_TESTS=true $(DOCKER_COMPOSE_TEST) run --rm test-runner

test-with-docker-unit: ## Run unit tests in isolated Docker container
	RUN_TESTS=true TEST_TYPE=unit $(DOCKER_COMPOSE_TEST) run --rm test-runner

test-with-docker-integration: ## Run integration tests in isolated Docker container
	RUN_TESTS=true TEST_TYPE=integration $(DOCKER_COMPOSE_TEST) run --rm test-runner

test-with-docker-component: ## Run component tests in isolated Docker container
	RUN_TESTS=true TEST_TYPE=component $(DOCKER_COMPOSE_TEST) run --rm test-runner

test-with-docker-end2end: ## Run end to end tests in isolated Docker container
	RUN_TESTS=true TEST_TYPE=end2end $(DOCKER_COMPOSE_TEST) run --rm test-runner

status: ## Show container status
	$(DOCKER_COMPOSE) ps

shell: ## Open shell in app container
	$(DOCKER_COMPOSE) exec app sh

redis-cli: ## Connect to Redis CLI
	$(DOCKER_COMPOSE) exec redis redis-cli

coverage: ## Run tests with coverage
	$(DOCKER_COMPOSE) exec app sh -c "cd /AuthService && uv run --python /AuthService/app/.venv/bin/python -m pytest tests/ -v --cov=app --cov-report=html --cov-report=term"

.PHONY: build
build: ## Build images without starting
	$(DOCKER_COMPOSE) build
