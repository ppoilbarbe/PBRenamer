PIXI := $(shell command -v pixi 2>/dev/null || echo "$(HOME)/.pixi/bin/pixi")
ifdef NOCONDA
CONDA_RUN  :=
else
CONDA_RUN  := $(PIXI) run --
endif
SRC        := src
DOCS       := docs
LOCALE_DIR := src/pbrenamer/locale
POT_FILE   := $(LOCALE_DIR)/pbrenamer.pot
PO_LOCALES := en fr de es it ru vi zh_CN

# ── Docs ─────────────────────────────────────────────────────────────────────
# Only the narrative pages (index.rst, user_guide.rst) are translated; the API
# reference (autodoc) and the changelog (generated, English only) are not.
# docs/locale/<lang>/LC_MESSAGES/ holds one sphinx-intl catalog per page,
# separate from the application catalogs under src/pbrenamer/locale/.
DOCS_LOCALE    := $(DOCS)/locale
DOC_LOCALES    := fr de es it ru vi zh_CN
# sphinx-build -b gettext takes individual source files, not a directory.
DOCS_NARRATIVE := $(DOCS)/index.rst $(DOCS)/user_guide.rst
# `make docs LANG=fr` builds a translated guide.  LANG is only honoured when
# given on the command line: it is also the standard locale variable (e.g.
# fr_FR.UTF-8), which make imports, and a plain `make docs` must build the
# English source whatever the user's locale.  It reaches conf.py as
# READTHEDOCS_LANGUAGE, as on Read the Docs.  make also exports command-line
# variables to recipes and sphinx-build fails on LANG=fr (not a valid system
# locale), hence DOC_ENV removing it from sphinx-build's environment.
DOC_LANG       := $(if $(filter command line,$(origin LANG)),$(LANG),en)
DOC_ENV        := $(if $(filter command line,$(origin LANG)),env -u LANG)
DOC_HTML       := $(DOCS)/_build/html$(if $(filter-out en,$(DOC_LANG)),-$(DOC_LANG))

R  := \033[0m
B  := \033[1m
G  := \033[32m
Y  := \033[33m
C  := \033[36m

# All Python sources (including *_ui.py which are now hand-written).
# Sorted: `find` order is filesystem-dependent, and pybabel's extraction
# order follows file processing order — an unsorted list makes `make
# translate` reorder .po entries on every run even with no string changes,
# dirtying the tree and breaking release version detection (git_version.sh).
PY_SOURCES := $(shell find $(SRC)/pbrenamer -name "*.py" \
                ! -path "*/__pycache__/*" | sort)

PO_FILES        := $(foreach lang,$(PO_LOCALES),$(LOCALE_DIR)/$(lang)/LC_MESSAGES/pbrenamer.po)
TRANSLATE_STAMP := .translate.stamp

.DEFAULT_GOAL := help
.PHONY: all help venv venv-update install translate new-lang run test perf coverage \
        hooks lint format docs docs-live docs-translate docs-stats dist srcdist clean force-translate \
        bump-major bump-minor bump-patch bump-set update-icons \
        pypi-build publish-pypi verify-pypi publish-testpypi verify-testpypi

all: translate ## Build all generated artifacts (strings → .mo)

help: ## This help
	@printf "$(B)$(C)PBRenamer — Development Tasks$(R)\n\n"
	@printf "$(Y)Usage:$(R) make $(G)<target>$(R)\n\n"
	@printf "$(Y)Targets:$(R)\n"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS=":.*?## "}; {printf "  $(G)%-14s$(R) %s\n", $$1, $$2}'
	@printf "\n$(Y)Variables:$(R)\n"
	@printf "  $(G)NOCONDA$(R)        Bypass pixi wrapping; tools must be on PATH\n"
	@printf "                 e.g. $(C)make test NOCONDA=1$(R)  or  $(C)export NOCONDA=1$(R)\n"

venv: ## Create/update the pixi environment from pyproject.toml (installs pixi if missing)
	@if ! command -v pixi >/dev/null 2>&1 && [ ! -x "$(PIXI)" ]; then \
		printf "$(C)pixi not found — installing...$(R)\n"; \
		curl -fsSL https://pixi.sh/install.sh | sh; \
	fi
	@printf "$(C)Installing pixi environment...$(R)\n"
	$(PIXI) install
	@printf "$(G)Done! Run tasks with:$(R) make <target>  (e.g. make run, make test)\n"

venv-update: ## Update the pixi environment / lockfile from pyproject.toml
	@printf "$(C)Updating pixi environment...$(R)\n"
	$(PIXI) update
	@printf "$(G)Done.$(R)\n"

# ── i18n ──────────────────────────────────────────────────────────────────────

translate: $(TRANSLATE_STAMP) ## Extract translatable strings, update .po files and compile .mo

$(TRANSLATE_STAMP): $(PY_SOURCES) $(PO_FILES)
	@printf "$(C)Extracting all translatable strings...$(R)\n"
	@printf '_("language_name")\n' > tools/_lang_name_stub.py
	$(CONDA_RUN) pybabel extract -F babel.cfg \
	    --copyright-holder="Marcel Spock" \
	    --msgid-bugs-address="mrspock@cardolan.net" \
	    --project="PBRenamer" \
	    --no-location \
	    -k _ -o $(POT_FILE) \
	    $(PY_SOURCES) tools/_lang_name_stub.py
	@rm -f tools/_lang_name_stub.py
	@printf "$(C)Updating .po files...$(R)\n"
	$(CONDA_RUN) pybabel update -i $(POT_FILE) -d $(LOCALE_DIR) \
	    -D pbrenamer --no-fuzzy-matching
	$(CONDA_RUN) python tools/fix_po_files.py $(LOCALE_DIR)
	@printf "$(C)Compiling .mo files...$(R)\n"
	$(CONDA_RUN) pybabel compile -d $(LOCALE_DIR) -D pbrenamer
	@printf "$(G)Done.$(R)\n"
	@touch $@

force-translate: ## Force-rebuild translations regardless of source changes
	@rm -f $(TRANSLATE_STAMP)
	@$(MAKE) translate

new-lang: ## Scaffold a new translation (usage: make new-lang LOCALE=de)
	@test -n "$(LOCALE)" || { \
	    printf "$(Y)Usage:$(R) make new-lang LOCALE=<lang-code>  (e.g. LOCALE=de)\n"; exit 1; }
	@test -f $(POT_FILE) || { \
	    printf "$(Y)Run 'make translate' first to generate the .pot template.$(R)\n"; exit 1; }
	$(CONDA_RUN) pybabel init -i $(POT_FILE) -d $(LOCALE_DIR) \
	    -D pbrenamer -l $(LOCALE)
	@printf "\n$(G)Created:$(R) $(LOCALE_DIR)/$(LOCALE)/LC_MESSAGES/pbrenamer.po\n\n"
	@printf "$(Y)Next steps:$(R)\n"
	@printf "  1. Edit the .po file and translate every msgstr entry.\n"
	@printf "  2. Set the $(B)language_name$(R) msgstr to the language's own name (e.g. 'Deutsch').\n"
	@printf "  3. Add $(B)$(LOCALE)$(R) to PO_LOCALES in the Makefile.\n"
	@printf "  4. Run: $(G)make translate$(R)\n"
	@printf "  5. Commit the .po and .mo files.\n"

# ── Development ───────────────────────────────────────────────────────────────

install: ## Install package in editable mode and register git hooks
	$(CONDA_RUN) pip install -e ".[dev]"
	$(CONDA_RUN) pre-commit install

run: ## Launch PBRenamer from the pixi env  (usage: make run ARGS="--debug /some/dir")
	$(CONDA_RUN) python -m pbrenamer $(ARGS)

test: ## Run test suite
	$(CONDA_RUN) pytest

perf: ## Run the performance tests (5,000 images; slow, not part of make test)
	$(CONDA_RUN) pytest -m perf -s --no-cov tests/perf

coverage: ## Run test suite and open HTML coverage report
	$(CONDA_RUN) pytest --cov-report=term-missing --cov-report=html
	@printf "$(G)Report:$(R) $(Y)htmlcov/index.html$(R)\n"

hooks: ## Run all pre-commit hooks on all files
	$(CONDA_RUN) pre-commit run --all-files

lint: ## Check code style
	$(CONDA_RUN) ruff check $(SRC)
	$(CONDA_RUN) ruff format --check $(SRC)

format: ## Auto-format source code
	$(CONDA_RUN) ruff format $(SRC)
	$(CONDA_RUN) ruff check --fix $(SRC)

docs: ## Build HTML documentation  (usage: make docs [LANG=fr], default en)
	@$(if $(filter $(DOC_LANG),en $(DOC_LOCALES)),:,\
	    printf "Unknown docs language '$(DOC_LANG)' (expected: en $(DOC_LOCALES))\n" >&2; exit 1)
	$(DOC_ENV) READTHEDOCS_LANGUAGE=$(DOC_LANG) $(CONDA_RUN) sphinx-build -b html $(DOCS) $(DOC_HTML)
	@printf "$(G)Open:$(R) $(DOC_HTML)/index.html\n"

docs-live: ## Build docs and watch for changes (hot reload)
	$(CONDA_RUN) sphinx-autobuild $(DOCS) $(DOCS)/_build/html

docs-translate: ## Extract the user guide strings and update docs/locale/*.po
	@printf "$(C)Extracting translatable strings from the narrative pages...$(R)\n"
	$(CONDA_RUN) sphinx-build -q -b gettext $(DOCS) $(DOCS)/_build/gettext $(DOCS_NARRATIVE)
	@printf "$(C)Updating $(DOCS_LOCALE)/*.po...$(R)\n"
	$(CONDA_RUN) sphinx-intl update -p $(DOCS)/_build/gettext -d $(DOCS_LOCALE) \
	    $(foreach lang,$(DOC_LOCALES),-l $(lang))
	$(CONDA_RUN) python tools/fix_po_files.py --docs $(DOCS_LOCALE)
	@printf "$(G)Done.$(R) Translate every new msgstr under $(Y)$(DOCS_LOCALE)/$(R).\n"

docs-stats: ## Report the user guide translation completeness
	$(CONDA_RUN) sphinx-intl stat -d $(DOCS_LOCALE)

update-icons: ## Sync app icon (.svg/.ico/.icns) from PBIcons
	$(CONDA_RUN) python tools/update_icons.py

# ── Distribution ──────────────────────────────────────────────────────────────

# PyInstaller builds natively: run this target on the target OS.
# Version comes from the exact git tag when HEAD is tagged and the tree is
# clean; otherwise "dev".  Output in dist/:
#   Linux   → dist/pbrenamer-<ver>-linux-x86_64
#   Windows → dist/pbrenamer-<ver>-windows-x86_64.exe
#   macOS   → dist/pbrenamer-<ver>-macos-arm64  (.app bundle)
dist: translate ## Build a standalone executable for the current platform
	@ver=$$(bash tools/git_version.sh); \
	printf "$(C)PyInstaller — version: $$ver  platform: $$($(CONDA_RUN) python -c 'import sys; print(sys.platform)')$(R)\n"; \
	mkdir -p dist; \
	PBRENAMER_VERSION=$$ver $(CONDA_RUN) pyinstaller --clean --noconfirm \
	    --distpath dist --workpath build/pyinstaller \
	    pbrenamer.spec
	@printf "$(G)Done.$(R) Executable in $(Y)dist/$(R)\n"

srcdist: ## Build a source archive (dist/pbrenamer-<ver>-src.tar.gz) via git archive
	@ver=$$(bash tools/git_version.sh); \
	out="dist/pbrenamer-$$ver-src.tar.gz"; \
	printf "$(C)Source archive — version: $$ver$(R)\n"; \
	mkdir -p dist; \
	git archive --format=tar.gz --prefix="pbrenamer-$$ver/" HEAD -o "$$out"; \
	printf "$(G)Done.$(R) Archive: $(Y)$$out$(R)\n"

# ── PyPI ──────────────────────────────────────────────────────────────────────

# Built into dist/pypi/ (not dist/) to avoid mixing with the PyInstaller
# executables and the git-archive source tarball, which also live in dist/.
# Version is the static `project.version` from pyproject.toml (via
# `make bump-*`) — unlike `dist`/`srcdist`, this must never fall back to
# "dev": PyPI permanently reserves whatever version number is uploaded.
pypi-build: ## Build wheel + sdist for PyPI (dist/pypi/*.whl, dist/pypi/*.tar.gz)
	@rm -rf dist/pypi
	@mkdir -p dist/pypi
	@printf "$(C)Building wheel + sdist for PyPI...$(R)\n"
	$(CONDA_RUN) python -m build --outdir dist/pypi
	@printf "$(G)Done.$(R) Artifacts in $(Y)dist/pypi/$(R)\n"

publish-pypi: pypi-build ## Upload wheel + sdist to the real PyPI — irreversible, asks for confirmation
	@printf "$(Y)About to upload dist/pypi/* to the REAL PyPI. This cannot be undone.$(R)\n"
	@read -p "Type 'yes' to continue: " confirm && [ "$$confirm" = "yes" ] || \
	    { printf "$(Y)Aborted.$(R)\n"; exit 1; }
	$(CONDA_RUN) twine upload dist/pypi/*
	@printf "$(G)Done.$(R)\n"

verify-pypi: ARGS ?= --version
verify-pypi: ## Install the latest real-PyPI package into a throwaway venv, smoke-test, then remove the venv (usage: make verify-pypi ARGS="--help-search")
	@venv_dir=$$(mktemp -d); \
	status=0; \
	printf "$(C)Creating throwaway venv: $$venv_dir$(R)\n"; \
	$(CONDA_RUN) python -m venv "$$venv_dir" || status=$$?; \
	if [ $$status -eq 0 ]; then \
	    printf "$(C)Installing pbrenamer from PyPI...$(R)\n"; \
	    "$$venv_dir/bin/pip" install pbrenamer || status=$$?; \
	fi; \
	if [ $$status -eq 0 ]; then \
	    printf "$(C)Running pbrenamer $(ARGS)...$(R)\n"; \
	    "$$venv_dir/bin/pbrenamer" $(ARGS) || status=$$?; \
	fi; \
	printf "$(C)Removing throwaway venv...$(R)\n"; \
	rm -rf "$$venv_dir"; \
	if [ $$status -eq 0 ]; then \
	    printf "$(G)Done.$(R) PyPI package installs and runs.\n"; \
	else \
	    printf "$(Y)Failed$(R) (exit $$status) — see output above.\n"; \
	    exit $$status; \
	fi

publish-testpypi: pypi-build ## Upload wheel + sdist to TestPyPI (requires TestPyPI credentials)
	@printf "$(C)Uploading to TestPyPI...$(R)\n"
	$(CONDA_RUN) twine upload --verbose --repository testpypi dist/pypi/*
	@printf "$(G)Done.$(R)\n"

verify-testpypi: ARGS ?= --version
verify-testpypi: ## Install the latest TestPyPI package into a throwaway venv, smoke-test, then remove the venv (usage: make verify-testpypi ARGS="--help-search")
	@venv_dir=$$(mktemp -d); \
	status=0; \
	printf "$(C)Creating throwaway venv: $$venv_dir$(R)\n"; \
	$(CONDA_RUN) python -m venv "$$venv_dir" || status=$$?; \
	if [ $$status -eq 0 ]; then \
	    printf "$(C)Installing pbrenamer from TestPyPI...$(R)\n"; \
	    "$$venv_dir/bin/pip" install \
	        --index-url https://test.pypi.org/simple/ \
	        --extra-index-url https://pypi.org/simple/ \
	        pbrenamer || status=$$?; \
	fi; \
	if [ $$status -eq 0 ]; then \
	    printf "$(C)Running pbrenamer $(ARGS)...$(R)\n"; \
	    "$$venv_dir/bin/pbrenamer" $(ARGS) || status=$$?; \
	fi; \
	printf "$(C)Removing throwaway venv...$(R)\n"; \
	rm -rf "$$venv_dir"; \
	if [ $$status -eq 0 ]; then \
	    printf "$(G)Done.$(R) TestPyPI package installs and runs.\n"; \
	else \
	    printf "$(Y)Failed$(R) (exit $$status) — see output above.\n"; \
	    exit $$status; \
	fi

# ── Versioning ────────────────────────────────────────────────────────────────

bump-major: ## Bump MAJOR version (x.0.0), reset minor and patch
	@$(CONDA_RUN) python tools/bump_version.py major

bump-minor: ## Bump MINOR version (x.y.0), reset patch
	@$(CONDA_RUN) python tools/bump_version.py minor

bump-patch: ## Bump PATCH version (x.y.z)
	@$(CONDA_RUN) python tools/bump_version.py patch

bump-set: ## Force a specific version (usage: make bump-set VERSION=x.y.z)
	@test -n "$(VERSION)" || { \
	    printf "$(Y)Usage:$(R) make bump-set VERSION=<x.y.z>\n"; exit 1; }
	@$(CONDA_RUN) python tools/bump_version.py set $(VERSION)

clean: ## Remove all build/cache artifacts
	rm -rf build dist *.egg-info .pytest_cache .coverage htmlcov $(DOCS)/_build
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -name "*.pyc" -delete
	rm -f $(POT_FILE) $(TRANSLATE_STAMP)
