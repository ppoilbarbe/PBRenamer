CONDA_ENV := pbrenamer
SRC       := src
DOCS      := docs

R  := \033[0m
B  := \033[1m
G  := \033[32m
Y  := \033[33m
C  := \033[36m

.DEFAULT_GOAL := help
.PHONY: help venv install run test lint format docs docs-live designer clean

help:
	@printf "$(B)$(C)PBRenamer — Development Tasks$(R)\n\n"
	@printf "$(Y)Usage:$(R) make $(G)<target>$(R)\n\n"
	@printf "$(Y)Targets:$(R)\n"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS=":.*?## "}; {printf "  $(G)%-14s$(R) %s\n", $$1, $$2}'

venv: ## Create conda env 'pbrenamer' with all dev dependencies
	@printf "$(C)Creating conda environment '$(CONDA_ENV)'...$(R)\n"
	conda create -n $(CONDA_ENV) -y -c conda-forge \
		python=3.12 \
		pyside6 \
		pytest pytest-qt pytest-cov \
		sphinx sphinx-rtd-theme sphinx-autobuild \
		ruff \
		gh
	conda run -n $(CONDA_ENV) pip install -e ".[dev]"
	@printf "$(G)Done! Activate with:$(R) conda activate $(CONDA_ENV)\n"

install: ## Install package in editable mode
	pip install -e ".[dev]"

run: ## Launch PBRenamer
	python -m pbrenamer

test: ## Run test suite
	pytest

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
