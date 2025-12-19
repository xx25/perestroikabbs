# Perestroika BBS Makefile
# Automated build, test, and deployment commands

.PHONY: help build up down test test-simple test-full clean logs shell migrate

# Default target
help:
	@echo "Perestroika BBS - Available Commands:"
	@echo "  make build       - Build Docker images"
	@echo "  make up          - Start BBS services"
	@echo "  make down        - Stop BBS services"
	@echo "  make test        - Run quick tests"
	@echo "  make test-full   - Run comprehensive tests"
	@echo "  make clean       - Clean up containers and volumes"
	@echo "  make logs        - Show BBS logs"
	@echo "  make shell       - Access BBS container shell"
	@echo "  make migrate     - Run database migrations"
	@echo "  make dev         - Start in development mode"
	@echo "  make prod        - Start in production mode"

# Build Docker images
build:
	docker compose build

# Start services
up:
	docker compose up -d
	@echo "BBS starting on port 2323..."
	@echo "MySQL on port 3307..."
	@echo "Run 'make logs' to view logs"

# Stop services
down:
	docker compose down

# Quick test
test: up
	@echo "Waiting for BBS to start..."
	@sleep 5
	@echo "Running basic tests..."
	@chmod +x tests/simple_test.sh
	@./tests/simple_test.sh || true
	@echo "Tests complete!"

# Simple tests only
test-simple:
	@chmod +x tests/simple_test.sh
	@./tests/simple_test.sh

# Comprehensive BBS functionality tests
test-all-features:
	@echo "Running comprehensive BBS feature tests..."
	@chmod +x tests/test_full_bbs.py
	@python3 tests/test_full_bbs.py || true

# End-to-end scenario tests
test-e2e:
	@echo "Running E2E scenario tests..."
	@chmod +x tests/test_e2e_scenarios.sh
	@./tests/test_e2e_scenarios.sh || true

# Comprehensive tests
test-full:
	@echo "Building test environment..."
	docker compose -f docker-compose.test.yml build
	@echo "Starting test services..."
	docker compose -f docker-compose.test.yml up -d
	@echo "Waiting for services..."
	@sleep 15
	@echo "Running comprehensive tests..."
	docker compose -f docker-compose.test.yml run --rm test-runner
	@echo "Cleaning up..."
	docker compose -f docker-compose.test.yml down

# Clean everything
clean:
	docker compose down -v
	docker compose -f docker-compose.test.yml down -v 2>/dev/null || true
	rm -rf test-results/
	@echo "Cleanup complete!"

# View logs
logs:
	docker compose logs -f bbs

# Access BBS shell
shell:
	docker compose exec bbs bash

# Run database migrations
migrate:
	docker compose exec bbs python -m alembic upgrade head

# Development mode
dev: down
	@echo "Starting in development mode..."
	docker compose up

# Production mode
prod: down
	@echo "Starting in production mode..."
	docker compose -f docker-compose.prod.yml up -d
	@echo "Production BBS started!"
	@echo "Run 'docker compose -f docker-compose.prod.yml logs -f' to view logs"

# Check BBS health
health:
	@echo "Checking BBS health..."
	@nc -zv localhost 2323 && echo "✓ BBS is responding on port 2323" || echo "✗ BBS not responding"
	@docker compose ps

# Run specific test file
test-file:
	@if [ -z "$(FILE)" ]; then \
		echo "Usage: make test-file FILE=tests/test_name.py"; \
	else \
		python3 $(FILE); \
	fi

# Performance test
test-perf:
	@echo "Running performance test..."
	@for i in {1..100}; do \
		(echo -e "\r\n" | timeout 1 nc localhost 2323 > /dev/null 2>&1 &); \
	done
	@sleep 5
	@echo "100 concurrent connections attempted"
	@docker compose exec bbs ps aux | grep python

# Database backup
backup:
	@echo "Creating database backup..."
	docker compose exec mysql mysqldump -u bbs_user -pbbspassword perestroika_bbs > backup-$$(date +%Y%m%d-%H%M%S).sql
	@echo "Backup complete!"

# Database restore
restore:
	@if [ -z "$(FILE)" ]; then \
		echo "Usage: make restore FILE=backup-file.sql"; \
	else \
		docker compose exec -T mysql mysql -u bbs_user -pbbspassword perestroika_bbs < $(FILE); \
		echo "Restore complete!"; \
	fi