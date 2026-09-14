.PHONY: build up down logs test clean help

help:
	@echo "ETHOS Core - Docker Commands"
	@echo "============================"
	@echo "make build           - Build Docker image"
	@echo "make up              - Start development environment"
	@echo "make up-prod         - Start production environment"
	@echo "make down            - Stop and remove containers"
	@echo "make logs            - View container logs"
	@echo "make test            - Run tests in container"
	@echo "make shell           - Open shell in running container"
	@echo "make clean           - Remove images and volumes"

build:
	docker build -t ethos-core:latest .

up:
	docker compose up -d
	@echo "Development environment started on http://localhost:8000"

up-prod:
	docker compose -f docker-compose.prod.yml up -d
	@echo "Production environment started"

down:
	docker compose down

logs:
	docker compose logs -f ethos-core --tail=100

test:
	docker compose exec ethos-core pytest tests/ -v

shell:
	docker compose exec ethos-core /bin/bash

clean:
	docker compose down -v
	docker rmi ethos-core:latest 2>/dev/null || true
	@echo "Cleanup complete"
