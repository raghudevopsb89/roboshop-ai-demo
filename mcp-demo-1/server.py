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
from starlette.responses import JSONResponse

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
ALLOWED_HOSTS = [h.strip() for h in os.environ.get("MCP_ALLOWED_HOSTS", "").split(",") if h.strip()]
ALLOWED_HOSTS += ["localhost", "localhost:*", "127.0.0.1", "127.0.0.1:*"]

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

    PUBLIC = {"/healthz"}

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
                         "tools": 4, "ts": int(time.time())})


def build_app():
    """The Starlette app, wrapped in auth and CORS. Importable for tests.

    Layer order matters. CORS must be OUTERMOST so that a browser's preflight
    OPTIONS -- which carries no Authorization header, by specification -- is
    answered before BearerAuth can 401 it. Get this backwards and MCP
    Inspector's web UI fails to connect with a bare CORS error and no clue why.
    """
    app = mcp.streamable_http_app(
        streamable_http_path=PATH,
        transport_security=TransportSecuritySettings(
            allowed_hosts=ALLOWED_HOSTS,
            allowed_origins=ALLOWED_ORIGINS,
        ),
    )
    app = BearerAuth(app, TOKEN)
    return CORSMiddleware(
        app,
        allow_origins=ALLOWED_ORIGINS,
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
    log.info("  hosts   : %s", ", ".join(ALLOWED_HOSTS))
    log.info("  origins : %s", ", ".join(ALLOWED_ORIGINS))
    log.info("  auth    : bearer token (%d chars)", len(TOKEN))
    log.info("inspect with:")
    log.info("  npx @modelcontextprotocol/inspector")
    log.info("  transport=HTTP  url=http://%s:%d%s  header Authorization: Bearer <token>",
             "localhost" if BIND_HOST in ("127.0.0.1", "0.0.0.0") else BIND_HOST, PORT, PATH)

    try:
        uvicorn.run(build_app(), host=BIND_HOST, port=PORT,
                    log_level=os.environ.get("MCP_LOG_LEVEL", "info").lower())
    finally:
        backend.close()


if __name__ == "__main__":
    main()
