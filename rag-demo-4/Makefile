VENV := .venv
PY   := $(VENV)/bin/python

# Only ask_live.py needs these. The RAG half is standard-library only and runs
# with plain python3.
venv:
	python3 -m venv $(VENV)
	$(VENV)/bin/pip install --quiet --upgrade pip
	$(VENV)/bin/pip install --quiet -r requirements.txt
	@echo "venv ready -- activate with: source $(VENV)/bin/activate"

check: ; $(PY) check_conn.py

live: ; $(PY) ask_live.py $(Q)

clean: ; rm -rf $(VENV) __pycache__

.PHONY: venv check live clean
