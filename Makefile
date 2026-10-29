.PHONY: run check test-unit test-contract test-int eval perf smoke lint format fixtures coverage provenance test-swap

PY := uv run

run:
	$(PY) -m cto_order_agent.main

check: lint provenance fixtures
	$(PY) pytest -q

lint:
	$(PY) ruff check src tests fixtures eval
	$(PY) mypy src/cto_order_agent

format:
	$(PY) ruff format src tests

test-unit:
	$(PY) pytest -q -m unit

test-contract:
	$(PY) pytest -q -m contract

test-int:
	$(PY) pytest -q -m integration

eval:
	$(PY) python eval/run_eval.py

perf:
	$(PY) python eval/perf.py

fixtures:
	$(PY) python fixtures/generate.py --check

provenance:
	@! grep -rn '\.source\s*==\|\["source"\]\s*==' src/ --include='*.py' | grep -v 'datasource/' || (echo "provenance branch detected" && false)
	@! grep -rn 'SYNTHETIC' src/ --include='*.py' | grep -v 'datasource/' || (echo "provenance constant leaked" && false)

coverage:
	$(PY) pytest -q --cov=cto_order_agent --cov-report=term-missing \
		--cov-fail-under=0
	$(PY) pytest -q --cov=cto_order_agent.domain.risk \
		--cov=cto_order_agent.domain.evidence --cov=cto_order_agent.narrative.validator \
		--cov-report=term-missing --cov-fail-under=100

test-swap:
	$(PY) pytest -q tests/contract/test_odata_mapping.py tests/unit/test_datasource_swap.py

smoke:
	@echo "boot the app, then curl /.well-known/agent-card.json and /healthz"
	$(PY) -c "from cto_order_agent.a2a.agent_card import build_agent_card; print(len(build_agent_card()['skills']), 'skills')"
