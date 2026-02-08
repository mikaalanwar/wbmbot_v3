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

.PHONY: dev deps run test add_user

dev:
	$(PIP) install -r $(REQ_FILE)

deps: dev

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
	@$(ENV_LOAD) $(PYTHON) $(PROJECT_DIR)/main.py $(RUN_ARGS)

test: deps
	@$(ENV_LOAD) $(PYTHON) -m unittest discover -s tests -p "test_*.py"

add_user: deps
	@$(ENV_LOAD) PYTHONPATH=$(PROJECT_DIR) $(PYTHON) $(PROJECT_DIR)/scripts/add_user.py $(filter-out $@,$(MAKECMDGOALS))

%:
	@:
