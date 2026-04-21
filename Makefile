CONDA_ENV := pbrenamer
SRC       := src
DOCS      := docs

R  := \033[0m
B  := \033[1m
G  := \033[32m
Y  := \033[33m
C  := \033[36m

UI_FILES := $(shell find $(SRC) -name "*.ui")
UI_PY    := $(UI_FILES:.ui=_ui.py)

.DEFAULT_GOAL := help
.PHONY: all help venv venv-update install ui run test lint format docs docs-live designer clean

all: ui ## Build all generated artifacts (UI → Python)

help:
	@printf "$(B)$(C)PBRenamer — Development Tasks$(R)\n\n"
	@printf "$(Y)Usage:$(R) make $(G)<target>$(R)\n\n"
	@printf "$(Y)Targets:$(R)\n"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS=":.*?## "}; {printf "  $(G)%-14s$(R) %s\n", $$1, $$2}'

venv: ## Create conda env 'pbrenamer' from environment.yml
	@printf "$(C)Creating conda environment '$(CONDA_ENV)'...$(R)\n"
	conda env create -f environment.yml
	@printf "$(G)Done! Activate with:$(R) conda activate $(CONDA_ENV)\n"

venv-update: ## Update existing conda env from environment.yml
	@printf "$(C)Updating conda environment '$(CONDA_ENV)'...$(R)\n"
	conda env update -f environment.yml --prune
	@printf "$(G)Done.$(R)\n"

ui: $(UI_PY) ## Compile all .ui files to Python via pyside6-uic

%_ui.py: %.ui
	@printf "$(C)uic:$(R) $< → $@\n"
	conda run -n $(CONDA_ENV) --no-capture-output pyside6-uic $< -o $@

install: ## Install package in editable mode and register git hooks
	pip install -e ".[dev]"
	pre-commit install

run: ## Launch PBRenamer from the conda env
	conda run -n $(CONDA_ENV) --no-capture-output python -m pbrenamer

test: ## Run test suite
	pytest

hooks: ## Run all pre-commit hooks on all files
	pre-commit run --all-files

lint: ## Check code style
	ruff check $(SRC)
	ruff format --check $(SRC)

format: ## Auto-format source code
	ruff format $(SRC)
	ruff check --fix $(SRC)

docs: ## Build HTML documentation
	sphinx-build -b html $(DOCS) $(DOCS)/_build/html
	@printf "$(G)Open:$(R) $(DOCS)/_build/html/index.html\n"

docs-live: ## Build docs and watch for changes (hot reload)
	sphinx-autobuild $(DOCS) $(DOCS)/_build/html

designer: ## Launch Qt Designer
	pyside6-designer

clean: ## Remove all build/cache artifacts
	rm -rf build dist *.egg-info .pytest_cache .coverage htmlcov $(DOCS)/_build
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -name "*.pyc" -delete
