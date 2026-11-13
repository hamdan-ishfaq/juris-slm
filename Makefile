.PHONY: up down rebuild logs ps migrate models verify e2e test test-unit test-integration eval-offline eval-logical eval-native eval-latency eval-ollama-full eval-full-local ingest-law fix-upload-perms airgap-bundle ui-dev ui-dev-stop ui-dev-restart ui-build ui-e2e airgap-eval brutal-gate retrieval-gate bench eval-proxy

COMPOSE = docker compose
API_URL = http://localhost:8002
# Host Python for scripts: python3.12 -m venv .venv (or uv venv -p 3.12 .venv), then install backend/requirements-ci.txt
PY = .venv/bin/python

up:
	$(COMPOSE) up -d --build --remove-orphans
	@echo "Waiting for API..."
	@for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do \
		curl -sf $(API_URL)/health >/dev/null 2>&1 && break; \
		sleep 2; \
	done
	@curl -sf $(API_URL)/health | python3 -m json.tool || (echo "API not ready" && exit 1)


mcp-up:
	$(COMPOSE) --profile mcp up -d mcp
	@echo "MCP server on http://localhost:8003/mcp (needs MCP_TOKEN_SHA256 and MCP_USER_EMAIL in .env; see scripts/mcp_token.py)"
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
	$(PY) scripts/download_assets.py --models --only bge-m3,reranker
	$(PY) scripts/verify_assets.py --models-only

verify:
	python3 scripts/verify_assets.py --models-only
	$(COMPOSE) ps
	@curl -sf $(API_URL)/health | python3 -m json.tool
	@curl -sf $(API_URL)/api/v1/status | python3 -m json.tool

check-llm-gpu:
	python3 scripts/check_llm_gpu.py

e2e:
	.venv/bin/python scripts/e2e_functional_test.py

test:
	cd backend && PYTHONPATH=src:tests ../.venv/bin/pytest tests/ -v --tb=short

test-unit:
	cd backend && PYTHONPATH=src:tests ../.venv/bin/pytest tests/test_access_control.py tests/test_security.py tests/test_rbac_eval.py tests/test_rrf.py tests/test_keyword_search.py tests/test_document_routing.py tests/test_rag_context.py tests/test_citation_verifier.py tests/test_law_chunking.py tests/test_law_download.py tests/test_contextual_retrieval.py tests/test_query_decompose.py tests/test_advanced_chunking.py tests/test_golden_datasets.py tests/test_eval_offline.py tests/test_dev_master.py tests/test_config_security.py tests/test_upload_security.py tests/test_eval_matching.py tests/test_llm_routing.py tests/test_playbook.py tests/test_rag_guards.py tests/test_answer_mode.py tests/test_ollama_options.py tests/test_ollama_chat.py tests/test_stage_timing.py tests/test_tracing.py tests/test_stream_verified.py tests/test_query_enhance.py tests/test_gap_analysis.py tests/test_contract_clauses.py tests/test_audit_chain.py tests/test_phase10.py tests/test_document_parser.py tests/test_law_references.py tests/test_law_graph.py tests/test_contract_review.py tests/test_mcp_server.py tests/test_upload_removal.py -v --tb=short

test-integration:
	cd backend && PYTHONPATH=src:tests ../.venv/bin/pytest tests/ -v -m integration --tb=short

eval-offline:
	.venv/bin/python scripts/run_logical_eval.py --offline

eval-logical:
	.venv/bin/python scripts/run_logical_eval.py --all

eval-proxy:
	.venv/bin/python scripts/run_context_proxy_eval.py --subset 15

eval-native:
	$(COMPOSE) run --rm --no-deps -T -e DATABASE_URL=postgresql+asyncpg://juris:juris_password@db:5432/juris_bench -v "$(CURDIR)/eval:/app/eval" api python eval/legalbench/legalbench.py answers
	.venv/bin/python scripts/run_native_ragas.py

retrieval-gate:
	$(COMPOSE) exec -T db sh -c "dropdb -U juris --if-exists juris_gate && createdb -U juris juris_gate"
	$(COMPOSE) exec -T -e DATABASE_URL=postgresql+asyncpg://juris:juris_password@db:5432/juris_gate api alembic upgrade head
	DATABASE_URL=postgresql+asyncpg://juris:juris_password@localhost:5433/juris_gate .venv/bin/python scripts/run_retrieval_gate.py

bench:
	bash scripts/bench.sh

eval-latency:
	.venv/bin/python scripts/run_latency_bench.py --chat-runs 5

eval-ollama-full:
	bash scripts/run_ollama_eval_complete.sh

eval-full-local:
	$(MAKE) eval-offline && $(MAKE) eval-logical && $(MAKE) eval-proxy && $(MAKE) eval-latency

eval-3x:
	for i in 1 2 3; do $(MAKE) eval-offline || exit 1; done

airgap-bundle:
	bash scripts/airgap_bundle.sh

ui-dev:
	bash scripts/ui_dev.sh

ui-dev-stop:
	bash scripts/ui_dev.sh --stop

ui-dev-restart:
	bash scripts/ui_dev.sh --restart

ui-build:
	cd frontend && npm install && npm run build

ui-e2e:
	cd frontend && npm install && npx playwright install chromium && npm run test:e2e

airgap-eval:
	LLM_PROVIDER=ollama bash scripts/airgap_eval.sh

gpu-build:
	$(COMPOSE) -f docker-compose.yml -f docker-compose.gpu.yml build api worker

gpu-up:
	$(COMPOSE) -f docker-compose.yml -f docker-compose.gpu.yml up -d --remove-orphans
	@echo "Waiting for API..."
	@for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do \
		curl -sf $(API_URL)/health >/dev/null 2>&1 && break; \
		sleep 2; \
	done
	@$(MAKE) verify-gpu

up-gpu: gpu-build gpu-up

.PHONY: up-gpu

verify-gpu:
	bash scripts/verify_gpu_stack.sh

brutal-gate:
	bash scripts/brutal_gate.sh

regulatory-diff:
	.venv/bin/python scripts/regulatory_diff.py

ingest-law:
	.venv/bin/python scripts/run_ingest_law.py --force

ingest-law-docker:
	$(COMPOSE) exec api python /app/src/ingest_law.py --force

download-law:
	$(PY) scripts/download_assets.py --datasets --only gdpr,bgb,bdsg,eu_ai_act

generate-golden:
	python3 scripts/generate_golden_datasets.py

fix-upload-perms:
	$(COMPOSE) run --user root --rm worker chown -R juris:juris /app/src/data/uploads
