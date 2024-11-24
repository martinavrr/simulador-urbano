.PHONY: clean data lint requirements sync_data_to_s3 sync_data_from_s3

#################################################################################
# GLOBALS                                                                       #
#################################################################################

PROJECT_DIR := $(shell dirname $(realpath $(lastword $(MAKEFILE_LIST))))
PROFILE = default
PROJECT_NAME = zorzim
PACKAGE_NAME = zorzim
ENV_NAME = zorzim
SRC_CODE_FOLDER = src/zorzim
PYTHON_INTERPRETER = python
CURRENT_ENV := $(CONDA_DEFAULT_ENV)

ifeq (,$(shell which mamba))
HAS_CONDA=False
else
HAS_CONDA=True
CONDA := $(shell which mamba)
ifeq ($(CONDA_DEFAULT_ENV),$(ENV_NAME))
ENV_IS_ACTIVE=True
else
ENV_IS_ACTIVE=False
endif
endif

#################################################################################
# COMMANDS                                                                      #
#################################################################################

## create conda environment
conda-create-env:
ifeq (True,$(HAS_CONDA))
	@printf ">>> Creating '$(ENV_NAME)' conda environment. This could take a few minutes ...\n\n"
	@$(CONDA) env create --name $(ENV_NAME) --file environment.yml
	@printf ">>> Adding the project to the environment...\n\n"
else
	@printf ">>> conda command not found. Check out that conda has been installed properly."
endif

## delete conda environment
conda-delete-env:
ifeq (True,$(HAS_CONDA))
	@printf ">>> Deleting '$(ENV_NAME)' conda environment. This could take a few minutes ...\n\n"
	@$(CONDA) env remove --name $(ENV_NAME)
	@printf ">>> Done.\n\n"
else
	@printf ">>> conda command not found. Check out that conda has been installed properly."
endif

## update conda environment
conda-update-env:
ifeq (True,$(HAS_CONDA))
	@printf ">>> Updating '$(ENV_NAME)' conda environment. This could take a few minutes ...\n\n"
	@$(CONDA) env update --name $(ENV_NAME) --file environment.yml --prune
	@printf ">>> Updated.\n\n"
else
	@printf ">>> conda command not found. Check out that conda has been installed properly."
endif

## install package in editable mode
install-package:
	conda run --name '$(ENV_NAME)' python -m pip install --editable .
	conda run --name '$(ENV_NAME)' python -m pip install --editable ./aves

## uninstall package
uninstall-package:
	conda run --name '$(ENV_NAME)' python -m pip uninstall --yes '$(PACKAGE_NAME)'
	conda run --name '$(ENV_NAME)' python -m pip uninstall --yes 'aves'

## install jupyter notebook kernel
install-kernel:
	conda run --name '$(ENV_NAME)' python -m ipykernel install --user --name '$(ENV_NAME)' --display-name "Python ($(ENV_NAME))"

## download data from external sources
download-external:
	sh ./scripts/download_osm.sh

## Install Python Dependencies
requirements: test_environment
	$(PYTHON_INTERPRETER) -m pip install -U pip setuptools wheel
	$(CONDA_DEFAULT_ENV) -m pip install -r requirements.txt

## Make Dataset
data: requirements
	$(PYTHON_INTERPRETER) src/data/make_dataset.py data/raw data/processed

## Delete all compiled Python files
clean:
	find . -type f -name "*.py[co]" -delete
	find . -type d -name "__pycache__" -delete

## Test python environment is setup correctly
test-environment:
	$(PYTHON_INTERPRETER) test_environment.py

#################################################################################
# PROJECT RULES                                                                 #
#################################################################################



#################################################################################
# Self Documenting Commands                                                     #
#################################################################################

.DEFAULT_GOAL := help

# Inspired by <http://marmelab.com/blog/2016/02/29/auto-documented-makefile.html>
# sed script explained:
# /^##/:
# 	* save line in hold space
# 	* purge line
# 	* Loop:
# 		* append newline + line to hold space
# 		* go to next line
# 		* if line starts with doc comment, strip comment character off and loop
# 	* remove target prerequisites
# 	* append hold space (+ newline) to line
# 	* replace newline plus comments by `---`
# 	* print line
# Separate expressions are necessary because labels cannot be delimited by
# semicolon; see <http://stackoverflow.com/a/11799865/1968>
.PHONY: help
help:
	@echo "$$(tput bold)Available rules:$$(tput sgr0)"
	@echo
	@sed -n -e "/^## / { \
		h; \
		s/.*//; \
		:doc" \
		-e "H; \
		n; \
		s/^## //; \
		t doc" \
		-e "s/:.*//; \
		G; \
		s/\\n## /---/; \
		s/\\n/ /g; \
		p; \
	}" ${MAKEFILE_LIST} \
	| LC_ALL='C' sort --ignore-case \
	| awk -F '---' \
		-v ncol=$$(tput cols) \
		-v indent=19 \
		-v col_on="$$(tput setaf 6)" \
		-v col_off="$$(tput sgr0)" \
	'{ \
		printf "%s%*s%s ", col_on, -indent, $$1, col_off; \
		n = split($$2, words, " "); \
		line_length = ncol - indent; \
		for (i = 1; i <= n; i++) { \
			line_length -= length(words[i]) + 1; \
			if (line_length <= 0) { \
				line_length = ncol - indent - length(words[i]) - 1; \
				printf "\n%*s ", -indent, " "; \
			} \
			printf "%s ", words[i]; \
		} \
		printf "\n"; \
	}' \
	| more $(shell test $(shell uname) = Darwin && echo '--no-init --raw-control-chars')
