# Expert System -- Makefile
#
# The interpreter is configurable because some machines expose Python as
# `python`, others as `python3`, others at a full path. Override like:
#     make test PYTHON=python
#     make test PYTHON=/c/Users/me/anaconda3/python.exe
PYTHON ?= python3

# Default file for `make run` (override with FILE=...).
FILE ?= examples/spec_consistent.txt

# Force UTF-8 so the --explain formal symbols print everywhere.
export PYTHONIOENCODING=utf-8

.PHONY: run test unit examples brute bonus clean help

help:
	@echo "Targets:"
	@echo "  make run   FILE=path   - run the engine on an input file"
	@echo "  make test              - run example tests + unit tests + brute-force"
	@echo "  make unit              - run only the unit tests"
	@echo "  make examples          - run only the example (end-to-end) tests"
	@echo "  make brute             - run only the brute-force cross-checker"
	@echo "  make bonus             - demo the bonus features (explain/debug/...)"
	@echo "  make clean             - remove __pycache__"

run:
	$(PYTHON) expert_system.py $(FILE)

test: examples unit brute

examples:
	$(PYTHON) tests/run_tests.py

unit:
	$(PYTHON) -m unittest tests.test_unit

brute:
	$(PYTHON) tests/bruteforce.py

bonus:
	@echo "===== --explain on the undetermined example ====="
	$(PYTHON) expert_system.py examples/undetermined.txt --explain
	@echo "===== --explain on a chain ====="
	$(PYTHON) expert_system.py examples/chain.txt --explain
	@echo "===== --debug (AST + graph) ====="
	$(PYTHON) expert_system.py examples/parentheses.txt --debug
	@echo "===== biconditional (both directions) ====="
	$(PYTHON) expert_system.py examples/bonus_biconditional_reverse.txt
	@echo "===== OR / XOR in conclusion ====="
	$(PYTHON) expert_system.py examples/bonus_or_conclusion.txt
	@echo "(try: make run FILE=examples/undetermined.txt then add --interactive)"

clean:
	rm -rf __pycache__ tests/__pycache__
