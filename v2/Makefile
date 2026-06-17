.PHONY: up down rebuild logs ps migrate models verify e2e ingest-law fix-upload-perms

COMPOSE = docker compose
API_URL = http://localhost:8002

up:
	$(COMPOSE) up -d --build --remove-orphans
	@echo "Waiting for API..."
	@for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do \
		curl -sf $(API_URL)/health >/dev/null 2>&1 && break; \
		sleep 2; \
	done
	@curl -sf $(API_URL)/health | python3 -m json.tool || (echo "API not ready" && exit 1)

down:
	$(COMPOSE) down

rebuild:
	$(COMPOSE) build --no-cache api worker
	$(COMPOSE) up -d --remove-orphans

logs:
	$(COMPOSE) logs -f api worker

ps:
	$(COMPOSE) ps

migrate:
	$(COMPOSE) exec api alembic upgrade head

models:
	python3 scripts/download_assets.py --models --only bge-m3,reranker
	python3 scripts/verify_assets.py --models-only

verify:
	python3 scripts/verify_assets.py --models-only
	$(COMPOSE) ps
	@curl -sf $(API_URL)/health | python3 -m json.tool
	@curl -sf $(API_URL)/api/v1/status | python3 -m json.tool

e2e:
	python3 scripts/e2e_functional_test.py

ingest-law:
	$(COMPOSE) exec api python /app/src/ingest_law.py

fix-upload-perms:
	$(COMPOSE) run --user root --rm worker chown -R juris:juris /app/src/data/uploads
