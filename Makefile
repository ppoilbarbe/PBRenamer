CONDA_ENV  := pbrenamer
ifdef NOCONDA
CONDA_RUN  :=
else
CONDA_RUN  := conda run -n $(CONDA_ENV) --no-capture-output
endif
SRC        := src
DOCS       := docs
LOCALE_DIR := src/pbrenamer/locale
POT_FILE   := $(LOCALE_DIR)/pbrenamer.pot
PO_LOCALES := en fr

R  := \033[0m
B  := \033[1m
G  := \033[32m
Y  := \033[33m
C  := \033[36m

UI_FILES := $(shell find $(SRC) -name "*.ui")
UI_PY    := $(UI_FILES:.ui=_ui.py)

# Python sources excluding auto-generated *_ui.py files
PY_SOURCES := $(shell find $(SRC)/pbrenamer -name "*.py" \
                ! -name "*_ui.py" ! -path "*/__pycache__/*")

PO_FILES        := $(foreach lang,$(PO_LOCALES),$(LOCALE_DIR)/$(lang)/LC_MESSAGES/pbrenamer.po)
TRANSLATE_STAMP := .translate.stamp

.DEFAULT_GOAL := help
.PHONY: all help venv venv-update install ui translate new-lang run test \
        lint format docs docs-live designer dist clean force-translate \
        bump-major bump-minor bump-patch bump-set

all: translate ## Build all generated artifacts (UI → Python, strings → .mo)

help: ## This help
	@printf "$(B)$(C)PBRenamer — Development Tasks$(R)\n\n"
	@printf "$(Y)Usage:$(R) make $(G)<target>$(R)\n\n"
	@printf "$(Y)Targets:$(R)\n"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS=":.*?## "}; {printf "  $(G)%-14s$(R) %s\n", $$1, $$2}'
	@printf "\n$(Y)Variables:$(R)\n"
	@printf "  $(G)NOCONDA$(R)        Bypass conda wrapping; tools must be on PATH\n"
	@printf "                 e.g. $(C)make test NOCONDA=1$(R)  or  $(C)export NOCONDA=1$(R)\n"

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
	$(CONDA_RUN) pyside6-uic $< -o $@

# ── i18n ──────────────────────────────────────────────────────────────────────

translate: $(TRANSLATE_STAMP) ## Extract translatable strings, update .po files and compile .mo

$(TRANSLATE_STAMP): $(UI_PY) $(PY_SOURCES) $(PO_FILES)
	@printf "$(C)Extracting from Python sources...$(R)\n"
	$(CONDA_RUN) xgettext --language=Python --keyword=_ \
	    --from-code=UTF-8 --package-name=pbrenamer \
	    --copyright-holder="Marcel Spock" \
	    --msgid-bugs-address="mrspock@cardolan.net" \
	    --output=$(POT_FILE) \
	    $(PY_SOURCES)
	@printf "$(C)Extracting from generated UI code...$(R)\n"
	$(CONDA_RUN) python tools/extract_ui_strings.py \
	    $(SRC)/pbrenamer/ui/main_window_ui.py > /tmp/_pbrenamer_ui_strings.py
	@echo '_("language_name")' >> /tmp/_pbrenamer_ui_strings.py
	$(CONDA_RUN) xgettext --language=Python --keyword=_ \
	    --from-code=UTF-8 --join-existing \
	    --output=$(POT_FILE) \
	    /tmp/_pbrenamer_ui_strings.py
	@rm -f /tmp/_pbrenamer_ui_strings.py
	@printf "$(C)Updating .po files...$(R)\n"
	@for lang in $(PO_LOCALES); do \
	    po=$(LOCALE_DIR)/$$lang/LC_MESSAGES/pbrenamer.po; \
	    if [ -f "$$po" ]; then \
	        $(CONDA_RUN) msgmerge --update --no-fuzzy-matching --backup=none \
	            "$$po" $(POT_FILE); \
	    fi; \
	done
	@printf "$(C)Compiling .mo files...$(R)\n"
	@for lang in $(PO_LOCALES); do \
	    po=$(LOCALE_DIR)/$$lang/LC_MESSAGES/pbrenamer.po; \
	    mo=$(LOCALE_DIR)/$$lang/LC_MESSAGES/pbrenamer.mo; \
	    $(CONDA_RUN) msgfmt "$$po" -o "$$mo" && printf "  $(G)$$mo$(R)\n"; \
	done
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
	@mkdir -p $(LOCALE_DIR)/$(LOCALE)/LC_MESSAGES
	$(CONDA_RUN) msginit --input=$(POT_FILE) --locale=$(LOCALE) --no-wrap \
	    --output=$(LOCALE_DIR)/$(LOCALE)/LC_MESSAGES/pbrenamer.po
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

run: ## Launch PBRenamer from the conda env
	$(CONDA_RUN) python -m pbrenamer

test: ## Run test suite
	$(CONDA_RUN) pytest

hooks: ## Run all pre-commit hooks on all files
	$(CONDA_RUN) pre-commit run --all-files

lint: ## Check code style
	$(CONDA_RUN) ruff check $(SRC)
	$(CONDA_RUN) ruff format --check $(SRC)

format: ## Auto-format source code
	$(CONDA_RUN) ruff format $(SRC)
	$(CONDA_RUN) ruff check --fix $(SRC)

docs: ## Build HTML documentation
	$(CONDA_RUN) sphinx-build -b html $(DOCS) $(DOCS)/_build/html
	@printf "$(G)Open:$(R) $(DOCS)/_build/html/index.html\n"

docs-live: ## Build docs and watch for changes (hot reload)
	$(CONDA_RUN) sphinx-autobuild $(DOCS) $(DOCS)/_build/html

designer: ## Launch Qt Designer
	$(CONDA_RUN) pyside6-designer

# ── Distribution ──────────────────────────────────────────────────────────────

# PyInstaller builds natively: run this target on the target OS.
# The output name embeds version + platform to allow mixed-OS dist/ directories.
#   Linux  → dist/PBRenamer-<ver>-linux-x86_64
#   Windows→ dist/PBRenamer-<ver>-windows-x86_64.exe
#   macOS  → dist/PBRenamer-<ver>-macos-arm64.app
dist: translate ## Build a standalone executable for the current platform
	@printf "$(C)PyInstaller — platform: $(shell $(CONDA_RUN) python -c 'import sys; print(sys.platform)')$(R)\n"
	$(CONDA_RUN) pyinstaller --clean --noconfirm \
	    --distpath dist --workpath build/pyinstaller \
	    pbrenamer.spec
	@printf "$(G)Done.$(R) Executable in $(Y)dist/$(R)\n"

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
	find . -name "*_ui.py" -delete
	rm -f $(POT_FILE) $(TRANSLATE_STAMP)
