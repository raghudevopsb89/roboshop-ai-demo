"""RoboShop MCP server -- a controlled access surface over private data.

The point of this demo, in one sentence: a teammate can ask questions about
live RoboShop data from their own AI tool, without ever holding the database
password or having access to the VNet.

    laptop (Claude Code / Claude Desktop / your own client)
        |  HTTPS + bearer token, NO database credentials
        v
    this server, on the RHEL VM, inside workstation-vnet
        |
        v
    private Azure MySQL + Cosmos

What the client can do is exactly four things -- ask for a product, a stock
level, sales for a SKU, or recent orders. It cannot send SQL. There is no
DROP TABLE reachable through get_stock(sku), because the only thing that
crosses the wire is a SKU string. And because every call lands here, every
call can be logged; a shared database password cannot be audited.

Usage:
    export MCP_TOKEN=$(openssl rand -hex 32)
    python3 server.py                          # live backend, localhost
    ROBOSHOP_BACKEND=sqlite python3 server.py  # rehearse with no VNet
"""
import hmac
import json
import logging
import os
import sys
import time

import uvicorn
from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import HTMLResponse, JSONResponse

import backend

# ---- configuration ------------------------------------------------------
TOKEN = os.environ.get("MCP_TOKEN", "")
BIND_HOST = os.environ.get("MCP_BIND_HOST", "127.0.0.1")
PORT = int(os.environ.get("MCP_PORT", "8080"))
PATH = os.environ.get("MCP_PATH", "/mcp")

# Streamable HTTP has DNS-rebinding protection on by default, and it rejects
# any Host header not in this list with "421 Invalid Host header". The default
# only covers localhost, so a laptop connecting to the VM by IP or DNS name is
# refused unless that name is listed here. This is the single most likely way
# to lose twenty minutes during the demo.
#   export MCP_ALLOWED_HOSTS="9.205.158.76:8080,roboshop-vm:8080"
_HOSTS_ENV = os.environ.get("MCP_ALLOWED_HOSTS", "")
ALLOWED_HOSTS = [h.strip() for h in _HOSTS_ENV.split(",") if h.strip()]
ALLOWED_HOSTS += ["localhost", "localhost:*", "127.0.0.1", "127.0.0.1:*"]

# Binding to anything other than loopback means remote clients, and a remote
# client's Host header is whatever address it dialled -- an IP, a DNS name, a
# load balancer. Listing them all up front is guesswork, and getting it wrong
# fails as "421 Invalid Host header" long after the token checked out.
#
# So when you bind publicly and have NOT pinned the list yourself, rebinding
# protection is switched off and any Origin is accepted. That protection exists
# to stop a malicious web page driving a server bound to a developer's
# localhost; it is not what is guarding this one. The bearer token is, and it
# is still required on every request.
OPEN_HOST = BIND_HOST not in ("127.0.0.1", "localhost", "::1")
PERMISSIVE = OPEN_HOST and not _HOSTS_ENV

# The same protection also checks Origin, and rejects an unlisted one with
# "403 Invalid Origin header". Server-to-server clients send no Origin and are
# unaffected, but MCP Inspector's web UI is a browser page -- so its origin has
# to be listed, and the endpoint needs CORS for the browser to read the reply.
# 6274 is Inspector's default UI port.
INSPECTOR_ORIGINS = ["http://localhost:6274", "http://127.0.0.1:6274"]
ALLOWED_ORIGINS = [o.strip() for o in os.environ.get("MCP_ALLOWED_ORIGINS", "").split(",") if o.strip()]
ALLOWED_ORIGINS += INSPECTOR_ORIGINS

logging.basicConfig(
    level=os.environ.get("MCP_LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)-5s %(message)s")
log = logging.getLogger("roboshop-mcp")

mcp = MCPServer(
    name="roboshop",
    instructions=(
        "Read-only access to the RoboShop store. Use these tools for any "
        "question about products, prices, stock levels, sales or orders. "
        "Report exactly what a tool returns; if it reports zero results, say "
        "so plainly rather than guessing."),
)


def _audit(tool, args, result):
    """One line per call. This is the audit trail a shared password cannot give.

    Arguments are logged; results are only summarised, so the log does not
    become a second copy of the database.
    """
    summary = "error" if isinstance(result, dict) and "error" in result else "ok"
    log.info("tool=%s args=%s -> %s", tool, json.dumps(args, default=str), summary)


# ---- the four tools -----------------------------------------------------
@mcp.tool()
def get_product(sku: str = "", name: str = "") -> dict:
    """Look up a RoboShop product by SKU (e.g. ROB007) or by name.

    Returns price, category, description and current stock.
    """
    out = backend.get_product(sku=sku or None, name=name or None)
    _audit("get_product", {"sku": sku, "name": name}, out)
    return out


@mcp.tool()
def get_stock(sku: str) -> dict:
    """Current stock level for one SKU, read live from the catalogue database.

    Use for any question about availability or how many units are left.
    """
    out = backend.get_stock(sku)
    _audit("get_stock", {"sku": sku}, out)
    return out


@mcp.tool()
def get_sales_for_sku(sku: str) -> dict:
    """Units sold and revenue for one SKU, from the live orders database.

    Use for any question about sales, revenue, or how well a product sells.
    """
    out = backend.get_sales_for_sku(sku)
    _audit("get_sales_for_sku", {"sku": sku}, out)
    return out


@mcp.tool()
def get_recent_orders(limit: int = 5) -> dict:
    """The most recent RoboShop orders, newest first (limit 1-25)."""
    out = backend.get_recent_orders(limit)
    _audit("get_recent_orders", {"limit": limit}, out)
    return out


# ---- authentication -----------------------------------------------------
class BearerAuth:
    """Reject anything without the shared token.

    Deliberately the simplest thing that works: one static token compared in
    constant time. The MCP spec's own scheme is OAuth 2.0 (MCPServer takes
    `auth=AuthSettings(...)` and a TokenVerifier), which needs a real issuer --
    more moving parts than this demo can justify. Swap it in if you take this
    past a demo.

    Everything is protected except the health endpoint, so a load balancer or
    a colleague can check liveness without holding the token.
    """

    # "/" is public and deliberately so: someone who pastes the server address
    # into a browser should be told what this is, not handed a bare 401.
    PUBLIC = {"/healthz", "/"}

    def __init__(self, app, token):
        self.app = app
        self.token = token

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope.get("path") in self.PUBLIC:
            return await self.app(scope, receive, send)

        headers = {k.lower(): v for k, v in scope.get("headers", [])}
        presented = headers.get(b"authorization", b"").decode(errors="replace")
        # compare_digest, not ==, so a wrong token cannot be recovered by
        # timing the response.
        if not hmac.compare_digest(presented, f"Bearer {self.token}"):
            log.warning("rejected unauthenticated request to %s from %s",
                        scope.get("path"), (scope.get("client") or ["?"])[0])
            response = JSONResponse(
                {"error": "unauthorized",
                 "detail": "send: Authorization: Bearer <MCP_TOKEN>"},
                status_code=401,
                headers={"WWW-Authenticate": 'Bearer realm="roboshop-mcp"'})
            return await response(scope, receive, send)

        return await self.app(scope, receive, send)


@mcp.custom_route("/healthz", methods=["GET"])
async def healthz(_request):
    """Unauthenticated liveness probe. Reveals the backend kind, never secrets."""
    return JSONResponse({"status": "ok", "backend": backend.BACKEND,
                         "tools": 4,
                         # "any" when bound publicly without a pinned host list;
                         # smoke_test.py checks the matching contract.
                         "host_check": "any" if PERMISSIVE else "pinned",
                         "ts": int(time.time())})


@mcp.custom_route("/", methods=["GET"])
async def index(request):
    """A signpost, not an app.

    Opening the server address in a browser is the obvious thing to try, and
    an MCP endpoint cannot answer it -- it is JSON-RPC over POST with a session
    handshake. Saying so here saves the "why do I get unauthorized" detour.
    Leaks nothing: no token, no connection strings.
    """
    host = request.headers.get("host", f"{BIND_HOST}:{PORT}")
    return HTMLResponse(f"""<!doctype html>
<meta charset="utf-8"><title>RoboShop MCP server</title>
<style>body{{font:15px/1.6 system-ui,sans-serif;max-width:44rem;margin:3rem auto;padding:0 1rem}}
code,pre{{background:#f4f4f5;border-radius:4px}} code{{padding:.1em .35em}}
pre{{padding:.8em;overflow-x:auto}} .m{{color:#666}}</style>
<h1>RoboShop MCP server</h1>
<p><strong>This is not a website.</strong> It is an MCP endpoint at
<code>/mcp</code> — JSON-RPC over POST, with a bearer token. There is no page
to browse here.</p>
<p>To use it, run MCP Inspector <em>on your own machine</em>:</p>
<pre>npx -y @modelcontextprotocol/inspector</pre>
<p>Then in the Inspector UI:</p>
<pre>Transport : Streamable HTTP
URL       : http://{host}/mcp
Header    : Authorization: Bearer &lt;your MCP_TOKEN&gt;</pre>
<p>Or without a browser:</p>
<pre>npx -y @modelcontextprotocol/inspector --cli \\
  --transport http --server-url http://{host}/mcp \\
  --header "Authorization: Bearer $MCP_TOKEN" \\
  --method tools/list</pre>
<p class="m">Tools: get_product, get_stock, get_sales_for_sku,
get_recent_orders &nbsp;·&nbsp; backend: {backend.BACKEND} &nbsp;·&nbsp;
liveness: <a href="/healthz">/healthz</a></p>
""")


def _public_address():
    """A host:port a client elsewhere can actually dial.

    0.0.0.0 is a bind address, not somewhere you can connect to -- printing it
    in the "use this URL" line sends people to a dead address. Prefer
    MCP_PUBLIC_HOST, else this machine's outward-facing IP, else the bind host.
    """
    explicit = os.environ.get("MCP_PUBLIC_HOST", "").strip()
    if explicit:
        return explicit
    if BIND_HOST not in ("0.0.0.0", "::"):
        return BIND_HOST
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # No packets are sent; this just asks the kernel which local address
        # would be used to reach the outside, which is the one to advertise.
        s.connect(("8.8.8.8", 53))
        return s.getsockname()[0]
    except OSError:
        return "localhost"
    finally:
        s.close()


def build_app():
    """The Starlette app, wrapped in auth and CORS. Importable for tests.

    Layer order matters. CORS must be OUTERMOST so that a browser's preflight
    OPTIONS -- which carries no Authorization header, by specification -- is
    answered before BearerAuth can 401 it. Get this backwards and MCP
    Inspector's web UI fails to connect with a bare CORS error and no clue why.
    """
    security = (TransportSecuritySettings(enable_dns_rebinding_protection=False)
                if PERMISSIVE else
                TransportSecuritySettings(allowed_hosts=ALLOWED_HOSTS,
                                          allowed_origins=ALLOWED_ORIGINS))
    app = mcp.streamable_http_app(streamable_http_path=PATH,
                                  transport_security=security)
    app = BearerAuth(app, TOKEN)
    return CORSMiddleware(
        app,
        allow_origins=["*"] if PERMISSIVE else ALLOWED_ORIGINS,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        # Without exposing this, the browser cannot read the session id off the
        # initialize response and every following request is "Missing session ID".
        expose_headers=["Mcp-Session-Id", "mcp-session-id"],
    )


def main():
    if not TOKEN:
        sys.exit(
            "MCP_TOKEN is not set -- refusing to start.\n\n"
            "An unauthenticated MCP server on a reachable port is an open door "
            "to your production data.\n"
            "  export MCP_TOKEN=$(openssl rand -hex 32)")
    if len(TOKEN) < 16:
        sys.exit(f"MCP_TOKEN is only {len(TOKEN)} characters -- use at least 16.")

    try:
        backend.check_config()
    except backend.ConfigError as e:
        sys.exit(str(e))

    log.info("roboshop-mcp starting")
    log.info("  backend : %s", backend.describe())
    log.info("  endpoint: http://%s:%d%s", BIND_HOST, PORT, PATH)
    if PERMISSIVE:
        log.info("  hosts   : any (bound to %s; the bearer token is the only guard)",
                 BIND_HOST)
        log.info("  origins : any")
    else:
        log.info("  hosts   : %s", ", ".join(ALLOWED_HOSTS))
        log.info("  origins : %s", ", ".join(ALLOWED_ORIGINS))
    log.info("  auth    : bearer token (%d chars)", len(TOKEN))

    if OPEN_HOST:
        log.warning("listening on %s -- reachable from off this machine.", BIND_HOST)
        log.warning("the token crosses the wire in cleartext over plain HTTP;")
        log.warning("keep the port scoped to people you trust, and rotate the token after.")

    advertise = _public_address()
    log.info("connect a client:")
    log.info("  npx -y @modelcontextprotocol/inspector")
    log.info("  transport = Streamable HTTP")
    log.info("  url       = http://%s:%d%s", advertise, PORT, PATH)
    log.info("  header    = Authorization: Bearer $MCP_TOKEN")

    try:
        uvicorn.run(build_app(), host=BIND_HOST, port=PORT,
                    log_level=os.environ.get("MCP_LOG_LEVEL", "info").lower())
    finally:
        backend.close()


if __name__ == "__main__":
    main()
