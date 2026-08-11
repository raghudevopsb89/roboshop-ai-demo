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

# Build the local roboshop.db from catalogue.sql + shipping.sql.
db: ; $(PY) setup_db.py

# Both run targets listen on all interfaces so a client on another machine can
# reach them with no tunnel. Override for a private run:  HOST=127.0.0.1 make run
HOST ?= 0.0.0.0

# Live data. Needs MYSQL_HOST / MYSQL_PASSWORD / MONGO_URL exported, and a host
# inside the VNet those private stores live in.
run: ; MCP_BIND_HOST=$(HOST) $(PY) server.py

# Rehearsal: local snapshot, no credentials, no VNet, runs anywhere.
run-sqlite: db
	MCP_BIND_HOST=$(HOST) ROBOSHOP_BACKEND=sqlite $(PY) server.py

# Detached: survives closing the SSH session. Use this on a server.
daemon: ; ./daemon.sh start
stop:   ; ./daemon.sh stop
status: ; ./daemon.sh status
logs:   ; ./daemon.sh log

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

.PHONY: venv token db run run-sqlite daemon stop status logs test inspect inspect-cli clean
