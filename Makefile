.PHONY: help setup setup-backend setup-frontend backend frontend demo demo-all test test-integration test-backend clean

PYTHON := python3
VENV_DIR := .venv
PIP := $(VENV_DIR)/bin/pip
PYTEST := $(VENV_DIR)/bin/pytest

help:
	@echo "EquiPay Commands"
	@echo "  make setup             - Install backend + frontend dependencies"
	@echo "  make backend           - Run backend (uvicorn reload)"
	@echo "  make frontend          - Run frontend (vite dev)"
	@echo "  make demo              - Run NovaBeat vendor demo server"
	@echo "  make demo-all          - Run backend + frontend + demo together"
	@echo "  make test              - Run backend test suite"
	@echo "  make test-integration  - Run live XRPL integration tests"
	@echo "  make clean             - Remove caches/build artifacts"

setup: setup-backend setup-frontend

setup-backend:
	$(PYTHON) -m venv $(VENV_DIR)
	$(PIP) install -r requirements.txt

setup-frontend:
	cd src/frontend && npm install

backend:
	cd src/backend/api && ../../../$(VENV_DIR)/bin/uvicorn main:app --reload --host 0.0.0.0 --port 8000

frontend:
	cd src/frontend && npm run dev -- --host 0.0.0.0 --port 5173

demo:
	cd src/demo/novabeat && EQUIPAY_BASE_URL=http://127.0.0.1:8000/api/v1 python3 server.py

demo-all:
	chmod +x scripts/dev/run_demo_all.sh
	./scripts/dev/run_demo_all.sh

test: test-backend

test-backend:
	$(PYTEST) -q src/backend/api/tests

test-integration:
	$(PYTEST) -q src/backend/api/tests/test_integration_testnet.py -m integration

clean:
	find . -type d -name "__pycache__" -prune -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf src/frontend/dist
