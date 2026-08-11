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
make run-sqlite          # builds the db, then serves on 0.0.0.0:8080
```

Both run targets listen on **all interfaces** so a client on another machine
connects directly, no tunnel. Keep it local with `HOST=127.0.0.1 make run-sqlite`.

On a cloud VM the machine only knows its private address, so the URL printed at
startup is the private one. Tell it the address clients actually dial:

```bash
export MCP_PUBLIC_HOST=9.205.88.27
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

**On a server**, `make run-sqlite` holds the terminal and dies with your SSH
session. Run it detached instead:

```bash
make daemon      # stops any old instance, starts detached, prints the pid
make status
make logs        # follow
make stop
```

`daemon.sh` generates a token into `.mcp_token` on first run (gitignored) and
reuses it after, so restarts do not invalidate a client you already configured.
Override with `MCP_TOKEN=... make daemon`.

Verify from another shell:

```bash
make test
```

It checks that `/healthz` is open, that a missing or wrong token gets 401, and
that a real MCP session can list and call tools. It exits non-zero if the auth
checks ever pass silently.

## Connect a client — MCP Inspector

**The server has no web UI.** Browsing to `http://<host>:8080/` gets you a page
that says so and repeats the settings below; `/mcp` itself is JSON-RPC over POST
and will only ever return `401` or `400` to a browser address bar. The UI is
Inspector, which you run yourself.

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
| `MCP_BIND_HOST` | `127.0.0.1` | the Makefile sets `0.0.0.0`; `HOST=` overrides |
| `MCP_PUBLIC_HOST` | auto-detected | address printed for clients to dial |
| `MCP_PORT` | `8080` | |
| `MCP_ALLOWED_HOSTS` | any, when bound publicly | setting it re-enables strict checks |
| `MCP_ALLOWED_ORIGINS` | any, when bound publicly | plus Inspector's `localhost:6274` |
| `ROBOSHOP_BACKEND` | `live` | or `sqlite` |
| `ROBOSHOP_SQLITE` | `./roboshop.db` | sqlite backend only |

## Host, Origin and the open port

Streamable HTTP ships with DNS-rebinding protection: it rejects an unknown
`Host` with `421` and an unknown `Origin` with `403`, *even when the token is
correct*, and neither error hints at why. A remote client's `Host` is whatever
address it dialled, so pinning that list up front is guesswork.

So when the server binds to anything other than loopback and you have **not**
set `MCP_ALLOWED_HOSTS` yourself, that protection is switched off and any
`Origin` is accepted. `/healthz` reports which mode you are in
(`"host_check": "any"` or `"pinned"`). That protection exists to stop a
malicious web page driving a server bound to someone's localhost; it is not
what guards this one. **The bearer token is**, and it is still required on
every request.

To pin them instead, set either and the strict behaviour returns:

```bash
export MCP_ALLOWED_HOSTS="9.205.88.27:8080,roboshop-vm:8080"
export MCP_ALLOWED_ORIGINS="http://192.168.1.20:6274"
```

**Understand what an open port means.** On a public IP with plain HTTP, the
token is the only thing between the internet and your data, and it crosses the
wire in cleartext. Scanners find open ports within minutes — the server log
shows them arriving:

```
WARNING rejected unauthenticated request to /favicon.ico from 165.22.120.45
```

That is the design working, but for anything beyond a demo put TLS in front of
it, scope the firewall to known addresses, and rotate the token afterwards.

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
| `daemon.sh` | start/stop/status/log, detached — for running on a server |
| `Makefile` | `venv`, `db`, `run`, `run-sqlite`, `daemon`, `stop`, `status`, `logs`, `test`, `inspect`, `inspect-cli` |

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
