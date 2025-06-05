-include .env
export

install:
	uv sync
.PHONY: install

pre-commit-setup:
	pre-commit install
.PHONY: pre-commit-setup


test:	
	uv run pytest lex/tests --cov=lex --cov-report=term-missing
.PHONY: test

run:
	uv run src/backend/main.py
.PHONY: run

# Pipeline data ingestion commands with memory optimization
ingest-caselaw:
	docker compose exec pipeline uv run src/lex/main.py -m caselaw --non-interactive --limit 50 --batch-size 20
.PHONY: pipeline-ingest-caselaw

ingest-caselaw-section:
	docker compose exec pipeline uv run src/lex/main.py -m caselaw-section --non-interactive --limit 50 
.PHONY: pipeline-ingest-caselaw-sections

ingest-legislation:
	docker compose exec pipeline uv run src/lex/main.py -m legislation --non-interactive --types ukpga --years 2020-2025 --limit 50
.PHONY: pipeline-ingest-legislation

ingest-legislation-section:
	docker compose exec pipeline uv run src/lex/main.py -m legislation-section --non-interactive --types ukpga --years 2020-2025 --limit 50
.PHONY: pipeline-ingest-legislation-sections

ingest-explanatory-note:
	docker compose exec pipeline uv run src/lex/main.py -m explanatory-note --non-interactive --types ukpga --years 2020-2025 --limit 50
.PHONY: pipeline-ingest-explanatory-notes

ingest-amendment:
	docker compose exec pipeline uv run src/lex/main.py -m amendment --non-interactive --years 2020-2025 --limit 250
.PHONY: pipeline-ingest-amendments

# Ingest all data in the pipeline
ingest-all: pipeline-ingest-legislation pipeline-ingest-legislation-section pipeline-ingest-explanatory-note pipeline-ingest-amendment pipeline-ingest-caselaw pipeline-ingest-caselaw-section
	@echo "All data types have been ingested."
.PHONY: pipeline-ingest-all

# Start Docker environment
docker-up:
	@echo "Starting Docker environment..."
	docker compose up -d
	@echo "Docker environment started. Waiting for Elasticsearch to be ready..."
	@echo "This may take up to 30 seconds on first startup..."
	@for i in $$(seq 1 6); do \
		if docker exec elasticsearch curl -s http://localhost:9200 > /dev/null; then \
			echo "Elasticsearch is ready!"; \
			break; \
		fi; \
		echo "Waiting for Elasticsearch to start... ($$i/6)"; \
		sleep 5; \
	done
	@echo "Ready to ingest data. Run 'make pipeline-ingest-all' to ingest all data."
.PHONY: docker-up

# Stop Docker environment
docker-down:
	docker compose down
.PHONY: docker-down