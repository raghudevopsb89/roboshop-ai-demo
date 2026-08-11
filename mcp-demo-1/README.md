# MCP server for RoboShop
---

The requirement: **let people ask questions about live RoboShop data from their
own AI tool, without giving anyone the database password or VNet access.**

Sharing a script that queries the databases directly cannot do that — running it
requires `MYSQL_PASSWORD` and `MONGO_URL` (which carries the Cosmos key), plus a
shell inside the VNet. Sharing the script means sharing admin credentials.

```
laptop: Claude Code / Claude Desktop / any MCP client
   |  HTTPS + bearer token, NO database credentials
   v
RHEL VM: this server, inside workstation-vnet
   |
   v
private Azure MySQL + Cosmos
```

The client gets four questions it may ask. Not a database session. It cannot
send SQL — the only thing crossing the wire is a SKU. And every call is logged,
which a shared password can never be.

## Tools

| Tool | Returns |
|---|---|
| `get_product(sku \| name)` | price, category, description, stock |
| `get_stock(sku)` | current stock |
| `get_sales_for_sku(sku)` | units sold, revenue |
| `get_recent_orders(limit)` | recent orders, newest first |

## Run it

```bash
make venv
eval "$(make -s token)"        # sets MCP_TOKEN; keep it, the client needs it
```

**Rehearsal** — no credentials, no VNet, runs anywhere. `make db` builds
`roboshop.db` from the `.sql` files in this directory:

```bash
make db
make run-sqlite
```

**Live** — needs three variables exported, and a host inside the VNet the
private MySQL and Cosmos endpoints live in:

```bash
export MYSQL_HOST=<mysql fqdn>
export MYSQL_PASSWORD=<password>
export MONGO_URL=<cosmos mongo connection string for the orders db>
make run
```

Everything in this README runs from this directory. Nothing else in the repo is
required.

Verify from another shell:

```bash
make test
```

It checks that `/healthz` is open, that a missing or wrong token gets 401, and
that a real MCP session can list and call tools. It exits non-zero if the auth
checks ever pass silently.

## Connect a client — MCP Inspector

Free, official, no account, no model. Needs `node`.

```bash
make inspect          # npx -y @modelcontextprotocol/inspector
```

It opens `http://localhost:6274`. In the UI:

| Field | Value |
|---|---|
| Transport | **Streamable HTTP** |
| URL | `http://localhost:8080/mcp` (or the VM's address) |
| Header | `Authorization` = `Bearer <your MCP_TOKEN>` |

Connect, then **List Tools** and call `get_stock` with `sku=ROB007`.

For teaching this beats a chat window: the raw `tools/list` response and the
JSON returned by a call are both on screen, so "MCP is plumbing, not
intelligence" is visible rather than asserted.

Same thing without a browser, which is useful for a quick check or a recording:

```bash
make inspect-cli                                  # tools/list
make inspect-cli TOOL=get_stock ARG=sku=ROB007    # call a tool
```

Any other MCP client works too — anything that speaks Streamable HTTP and can
send an `Authorization` header. Clients that only speak stdio need a bridge such
as `npx mcp-remote <url> --header ...`.

## Settings

| Variable | Default | Notes |
|---|---|---|
| `MCP_TOKEN` | — | **required**, ≥16 chars; server refuses to start without it |
| `MCP_BIND_HOST` | `127.0.0.1` | `0.0.0.0` to accept remote clients |
| `MCP_PORT` | `8080` | |
| `MCP_ALLOWED_HOSTS` | — | see below |
| `MCP_ALLOWED_ORIGINS` | Inspector's `localhost:6274` | extra browser origins |
| `ROBOSHOP_BACKEND` | `live` | or `sqlite` |
| `ROBOSHOP_SQLITE` | `./roboshop.db` | sqlite backend only |

## Three gotchas

**`421 Invalid Host header`.** Streamable HTTP has DNS-rebinding protection on
by default and only trusts localhost. A laptop connecting to the VM by IP is
refused *even with a correct token*, and the error says nothing about why. Put
the address clients actually use in `MCP_ALLOWED_HOSTS`:

```bash
export MCP_ALLOWED_HOSTS="9.205.158.76:8080,roboshop-vm:8080"
```

**`403 Invalid Origin header`.** The same protection also checks `Origin`.
Server-to-server clients send none and never see this; a browser always sends
one. Inspector's default `http://localhost:6274` is allowed out of the box — if
you run its UI anywhere else, add it:

```bash
export MCP_ALLOWED_ORIGINS="http://192.168.1.20:6274"
```

The endpoint also answers CORS preflight, and that layer sits **outside** auth
deliberately: a preflight `OPTIONS` carries no `Authorization` header by
specification, so authenticating it would break every browser client with an
opaque CORS error. `Mcp-Session-Id` is in `Access-Control-Expose-Headers` for
the same class of reason — without it the browser cannot read the session id
and every request after `initialize` fails with *Missing session ID*.

**Auth is a single static token**, compared in constant time. That is the
simplest thing that closes the open door, and it is the whole security model —
anyone with the token gets all four tools. The MCP spec's own scheme is OAuth
2.0 (`MCPServer(auth=AuthSettings(...), token_verifier=...)`), which needs a
real issuer. Worth doing if this outlives the demo. Also put TLS in front of it
before it carries anything you care about; the token crosses the wire in a
header.

## Files

| File | Role |
|---|---|
| `server.py` | the MCP server — four tools, bearer auth, audit logging |
| `backend.py` | data access; the only place credentials exist |
| `setup_db.py` | builds `roboshop.db` for the sqlite backend |
| `catalogue.sql`, `shipping.sql` | the data — 12 products, 25 cities |
| `smoke_test.py` | proves the tools work *and* that the token protects them |
| `Makefile` | `venv`, `token`, `db`, `run`, `run-sqlite`, `test`, `inspect`, `inspect-cli` |

## Demo running order

All from this directory.

```bash
make venv && eval "$(make -s token)"
make run-sqlite                 # or: make run, with the live variables set
make test                       # in a second shell: everything green
make inspect                    # browser: list the tools, call one
```

Talking points, in order: the server holds the credentials; the client holds a
token and nothing else; the client can ask exactly four questions and cannot
send SQL; every call is logged on the server (`tool=get_stock args=... -> ok`),
which a shared database password can never be.
