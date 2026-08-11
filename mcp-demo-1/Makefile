VENV := .venv
PY   := $(VENV)/bin/python

venv:
	python3 -m venv $(VENV)
	$(VENV)/bin/pip install --quiet --upgrade pip
	$(VENV)/bin/pip install --quiet -r requirements.txt
	@echo "venv ready"

# A fresh token. Copy the export line into the server shell and the client config.
token:
	@echo "export MCP_TOKEN=$$($(PY) -c 'import secrets;print(secrets.token_hex(32))')"

# Live data. Needs MYSQL_* / MONGO_URL and must run on the VM.
run: ; $(PY) server.py

# Rehearsal: the rag-demo-4 snapshot, no credentials, no VNet, runs anywhere.
run-sqlite: ; ROBOSHOP_BACKEND=sqlite $(PY) server.py

test: ; $(PY) smoke_test.py

URL ?= http://localhost:8080/mcp

# MCP Inspector web UI. Needs node, no install, no account.
# In the UI: Transport = "Streamable HTTP", URL as below, and add a header
#   Authorization: Bearer $$MCP_TOKEN
inspect:
	npx -y @modelcontextprotocol/inspector

# Same thing without a browser -- handy to prove the server works over HTTP.
#   make inspect-cli                       (tools/list)
#   make inspect-cli TOOL=get_stock ARG=sku=ROB007
inspect-cli:
	@test -n "$(MCP_TOKEN)" || { echo "MCP_TOKEN not set"; exit 1; }
	npx -y @modelcontextprotocol/inspector --cli \
	  --transport http --server-url $(URL) \
	  --header "Authorization: Bearer $(MCP_TOKEN)" \
	  $(if $(TOOL),--method tools/call --tool-name $(TOOL) --tool-arg $(ARG),--method tools/list)

clean: ; rm -rf $(VENV) __pycache__

.PHONY: venv token run run-sqlite test inspect inspect-cli clean
