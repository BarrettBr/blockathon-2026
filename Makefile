.PHONY: help setup setup-backend setup-frontend backend frontend test test-integration test-backend clean

PYTHON := python3
VENV_DIR := .venv
PIP := $(VENV_DIR)/bin/pip
PYTEST := $(VENV_DIR)/bin/pytest

help:
	@echo "EquiPay Commands"
	@echo "  make setup             - Install backend + frontend dependencies"
	@echo "  make backend           - Run backend (uvicorn reload)"
	@echo "  make frontend          - Run frontend (vite dev)"
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
	cd src/backend/api && ../../../$(VENV_DIR)/bin/uvicorn main:app --reload

frontend:
	cd src/frontend && npm run dev

test: test-backend

test-backend:
	$(PYTEST) -q src/backend/api/tests

test-integration:
	$(PYTEST) -q src/backend/api/tests/test_integration_testnet.py -m integration

clean:
	find . -type d -name "__pycache__" -prune -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf src/frontend/dist
