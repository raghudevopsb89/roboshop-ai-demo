VENV := .venv
PY   := $(VENV)/bin/python
PIP  := $(VENV)/bin/pip

.PHONY: venv check ask clean

# RHEL 10 marks the system Python as externally managed (PEP 668), so pip
# refuses to install into it. A venv sidesteps that cleanly.
venv:
	python3 -m venv $(VENV)
	$(PIP) install --quiet --upgrade pip
	$(PIP) install --quiet -r requirements.txt
	@echo "venv ready -- activate with: source $(VENV)/bin/activate"

check: ; $(PY) check_conn.py

ask: ; $(PY) ask_live.py $(Q)

clean: ; rm -rf $(VENV) __pycache__
