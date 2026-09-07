PYTHON ?= python3
.PHONY: check bundle
check:
	$(PYTHON) tools/build_bundle.py --check
	$(PYTHON) -m resume_contracts.verify
	$(PYTHON) -m unittest discover -s tests
bundle:
	$(PYTHON) tools/build_bundle.py
