.PHONY: up down seed test eval tf-init tf-validate help

help:
	@echo "Available commands:"
	@echo "  make up          - Start all Docker containers (PostgreSQL, Redis, Backend, Frontend)"
	@echo "  make down        - Stop and remove all containers and volumes"
	@echo "  make seed        - Generate synthetic SQL data (5 balanced channels, anomalies)"
	@echo "  make test        - Run all 28 unit, multi-turn, logging, and guardrail tests"
	@echo "  make eval        - Run automated evaluation harness on all 10 test scenarios"
	@echo "  make tf-init     - Initialize Azure Terraform providers in infra/terraform"
	@echo "  make tf-validate - Format check and validate Azure Terraform configuration"

up:
	docker compose -f infra/docker-compose.yml up --build -d

down:
	docker compose -f infra/docker-compose.yml down -v

seed:
	python3 db/seed/generate_data.py

test:
	PYTHONPATH=. .venv/bin/python3 -m unittest discover -s backend/tests

eval:
	PYTHONPATH=. .venv/bin/python3 backend/eval/eval_harness.py

tf-init:
	cd infra/terraform && terraform init -backend=false

tf-validate:
	cd infra/terraform && terraform fmt -check && terraform validate
