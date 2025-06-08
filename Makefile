-include .env
export

# Get current year dynamically
CURRENT_YEAR := $(shell date +%Y)

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

# Pipeline data ingestion commands - SAMPLE (limited data for testing)
ingest-caselaw-sample:
	docker compose exec pipeline uv run src/lex/main.py -m caselaw --non-interactive --years 2020-$(CURRENT_YEAR) --limit 50 --batch-size 20
.PHONY: ingest-caselaw-sample

ingest-caselaw-section-sample:
	docker compose exec pipeline uv run src/lex/main.py -m caselaw-section --non-interactive --years 2020-$(CURRENT_YEAR) --limit 50
.PHONY: ingest-caselaw-section-sample

ingest-legislation-sample:
	docker compose exec pipeline uv run src/lex/main.py -m legislation --non-interactive --types ukpga --years 2020-$(CURRENT_YEAR) --limit 50
.PHONY: ingest-legislation-sample

ingest-legislation-section-sample:
	docker compose exec pipeline uv run src/lex/main.py -m legislation-section --non-interactive --types ukpga --years 2020-$(CURRENT_YEAR) --limit 50
.PHONY: ingest-legislation-section-sample

ingest-explanatory-note-sample:
	docker compose exec pipeline uv run src/lex/main.py -m explanatory-note --non-interactive --types ukpga --years 2020-$(CURRENT_YEAR) --limit 50
.PHONY: ingest-explanatory-note-sample

ingest-amendment-sample:
	docker compose exec pipeline uv run src/lex/main.py -m amendment --non-interactive --years 2020-$(CURRENT_YEAR) --limit 250
.PHONY: ingest-amendment-sample

# Ingest all sample data
ingest-all-sample: ingest-legislation-sample ingest-legislation-section-sample ingest-explanatory-note-sample ingest-amendment-sample ingest-caselaw-sample ingest-caselaw-section-sample
	@echo "All sample data types have been ingested."
.PHONY: ingest-all-sample

# Pipeline data ingestion commands - FULL (all types, legislation from 1963, caselaw from 2001)
ingest-caselaw-full:
	docker compose exec pipeline uv run src/lex/main.py -m caselaw --non-interactive --years 2001-$(CURRENT_YEAR) --batch-size 50
.PHONY: ingest-caselaw-full

ingest-caselaw-section-full:
	docker compose exec pipeline uv run src/lex/main.py -m caselaw-section --non-interactive --years 2001-$(CURRENT_YEAR) --batch-size 50
.PHONY: ingest-caselaw-section-full

ingest-legislation-full:
	docker compose exec pipeline uv run src/lex/main.py -m legislation --non-interactive --years 1963-$(CURRENT_YEAR) --batch-size 50
.PHONY: ingest-legislation-full

ingest-legislation-section-full:
	docker compose exec pipeline uv run src/lex/main.py -m legislation-section --non-interactive --years 1963-$(CURRENT_YEAR) --batch-size 50
.PHONY: ingest-legislation-section-full

ingest-explanatory-note-full:
	docker compose exec pipeline uv run src/lex/main.py -m explanatory-note --non-interactive --years 1963-$(CURRENT_YEAR) --batch-size 50
.PHONY: ingest-explanatory-note-full

ingest-amendment-full:
	docker compose exec pipeline uv run src/lex/main.py -m amendment --non-interactive --years 1963-$(CURRENT_YEAR) --batch-size 50
.PHONY: ingest-amendment-full

# Ingest all full data
ingest-all-full: ingest-legislation-full ingest-legislation-section-full ingest-explanatory-note-full ingest-amendment-full ingest-caselaw-full ingest-caselaw-section-full
	@echo "All full data types have been ingested."
.PHONY: ingest-all-full

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
	@echo "Ready to ingest data. Run 'make ingest-all-sample' for sample data or 'make ingest-all-full' for full data."
.PHONY: docker-up

# Stop Docker environment
docker-down:
	docker compose down
.PHONY: docker-down
