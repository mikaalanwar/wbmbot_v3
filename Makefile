ifneq (,$(wildcard .env))
include .env
ENV_VARS := $(shell sed -n 's/^\([A-Za-z_][A-Za-z0-9_]*\)=.*/\1/p' .env)
export $(ENV_VARS)
endif

PYENV_CMD := $(shell command -v pyenv 2>/dev/null)
ifdef PYENV_CMD
PYENV_PYTHON := $(shell pyenv exec python -c 'import sys; print(sys.executable)' 2>/dev/null)
endif
DEFAULT_PYTHON := $(shell if command -v python3 >/dev/null 2>&1; then command -v python3; elif command -v python >/dev/null 2>&1; then command -v python; else echo python3; fi)
ifeq ($(origin PYTHON), undefined)
PYTHON := $(if $(strip $(PYENV_PYTHON)),$(PYENV_PYTHON),$(DEFAULT_PYTHON))
else
PYTHON_PATH := $(shell if command -v "$(PYTHON)" >/dev/null 2>&1; then command -v "$(PYTHON)"; fi)
PYTHON := $(if $(strip $(PYTHON_PATH)),$(PYTHON_PATH),$(if $(strip $(PYENV_PYTHON)),$(PYENV_PYTHON),$(DEFAULT_PYTHON)))
endif
PIP := $(PYTHON) -m pip
PROJECT_DIR := wbmbot_v3
REQ_FILE := $(PROJECT_DIR)/requirements.txt
DEV_REQ_FILE := requirements-dev.txt

.PHONY: dev deps run test lint typecheck check add_user

deps:
	$(PIP) install -r $(REQ_FILE)

dev:
	$(PIP) install -r $(DEV_REQ_FILE)

ENV_LOAD := if [ -f .env ]; then set -a; . ./.env; set +a; fi;
DEBUG_FLAG :=
ifneq ($(filter --debug%,$(MAKEFLAGS)),)
DEBUG_FLAG := --debug
endif
ifneq ($(filter d,$(MAKEFLAGS)),)
DEBUG_FLAG := --debug
endif
ifeq ($(DEBUG),1)
DEBUG_FLAG := --debug
endif

RUN_ARGS := $(ARGS)
ifneq ($(strip $(DEBUG_FLAG)),)
ifeq ($(findstring --debug,$(RUN_ARGS)),)
RUN_ARGS := $(RUN_ARGS) $(DEBUG_FLAG)
endif
endif

run: deps
	@$(ENV_LOAD) $(PYTHON) -m $(PROJECT_DIR) $(RUN_ARGS)

test: dev
	@$(ENV_LOAD) $(PYTHON) -m pytest -q

lint: dev
	@$(ENV_LOAD) $(PYTHON) -m ruff check .

typecheck: dev
	@$(ENV_LOAD) $(PYTHON) -m mypy

check: lint typecheck test

add_user: deps
	@$(ENV_LOAD) $(PYTHON) -m $(PROJECT_DIR).scripts.add_user $(filter-out $@,$(MAKECMDGOALS))

%:
	@:
