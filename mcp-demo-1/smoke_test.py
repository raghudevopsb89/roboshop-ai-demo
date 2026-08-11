"""Prove the server works and that the token actually protects it.

Run it against a server you started separately:

    MCP_TOKEN=... python3 smoke_test.py
    MCP_URL=http://9.205.158.76:8080/mcp MCP_TOKEN=... python3 smoke_test.py

Checks, in order:
  1. /healthz answers WITHOUT a token          (liveness must not need the secret)
  2. /mcp is refused with NO token             -> 401
  3. /mcp is refused with the WRONG token      -> 401
  4. with the right token: initialize + tools/list
  5. a real tool call returns real data

Steps 2 and 3 are the demo's security claim. If they ever pass silently, the
server is an open door and the whole premise is void -- so this exits non-zero.
"""
import asyncio
import os
import sys

import httpx2
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

URL = os.environ.get("MCP_URL", "http://127.0.0.1:8080/mcp")
TOKEN = os.environ.get("MCP_TOKEN", "")
HEALTH = URL.rsplit("/", 1)[0] + "/healthz"

PASS, FAIL = "  ok  ", " FAIL "
failures = []


def check(ok, label, detail=""):
    print(f"[{PASS if ok else FAIL}] {label}" + (f"\n         {detail}" if detail else ""))
    if not ok:
        failures.append(label)


async def main():
    if not TOKEN:
        sys.exit("MCP_TOKEN not set -- use the same value the server was started with")

    print(f"target: {URL}\n")

    # 1. health, unauthenticated
    async with httpx2.AsyncClient(timeout=10) as http:
        try:
            r = await http.get(HEALTH)
            check(r.status_code == 200, "health endpoint open without a token",
                  f"{r.status_code} {r.text[:120]}")
            # Bound publicly without a pinned host list -> any Host/Origin is
            # accepted on purpose, so the Origin expectation below flips.
            try:
                pinned = r.json().get("host_check") == "pinned"
            except Exception:
                pinned = True
        except Exception as e:
            check(False, "health endpoint reachable", f"{type(e).__name__}: {e}")
            print("\nserver not running? start it in another shell:\n"
                  "  ROBOSHOP_BACKEND=sqlite MCP_TOKEN=$MCP_TOKEN python3 server.py")
            return 1

        # 2 + 3. the MCP endpoint must refuse bad credentials
        probe = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
        accept = {"Accept": "application/json, text/event-stream",
                  "Content-Type": "application/json"}
        r = await http.post(URL, json=probe, headers=accept)
        check(r.status_code == 401, "no token is rejected", f"got HTTP {r.status_code}")

        r = await http.post(URL, json=probe,
                            headers={**accept, "Authorization": "Bearer wrong-token"})
        check(r.status_code == 401, "wrong token is rejected", f"got HTTP {r.status_code}")

        # --- the browser path, used by MCP Inspector's web UI ---
        # An unlisted Origin must be refused (403), Inspector's must not be,
        # and the preflight must succeed WITHOUT a token -- OPTIONS carries no
        # Authorization header by specification.
        inspector = "http://localhost:6274"
        r = await http.post(URL, json=probe, headers={
            **accept, "Authorization": f"Bearer {TOKEN}", "Origin": "http://evil.example"})
        if pinned:
            check(r.status_code == 403, "unlisted Origin is rejected",
                  f"got HTTP {r.status_code}")
        else:
            check(r.status_code != 403,
                  "any Origin accepted (server bound publicly, host_check=any)",
                  f"got HTTP {r.status_code} -- the token is the guard here")

        r = await http.request("OPTIONS", URL, headers={
            "Origin": inspector,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type"})
        allow = r.headers.get("access-control-allow-origin", "")
        check(r.status_code < 400 and allow in (inspector, "*"),
              "CORS preflight succeeds without a token",
              f"HTTP {r.status_code} allow-origin={allow!r}")

        r = await http.post(URL, json=probe, headers={
            **accept, "Authorization": f"Bearer {TOKEN}", "Origin": inspector})
        check(r.status_code != 403, "Inspector Origin is accepted",
              f"got HTTP {r.status_code} (403 would mean the origin is blocked)")
        # Expose-Headers belongs on the real response, not the preflight. Without
        # it the browser cannot read the session id and every later request
        # fails with "Missing session ID".
        exposed = r.headers.get("access-control-expose-headers", "")
        check("mcp-session-id" in exposed.lower(),
              "session id header is exposed to the browser", exposed or "(none)")

    # 4 + 5. a real MCP session
    auth = {"Authorization": f"Bearer {TOKEN}"}
    async with httpx2.AsyncClient(headers=auth, timeout=30) as http:
        async with streamable_http_client(URL, http_client=http) as (read, write):
            async with ClientSession(read, write) as session:
                info = await session.initialize()
                si = info.server_info
                check(True, "initialize", f"server: {si.name} v{si.version or '0'}")

                listed = await session.list_tools()
                names = sorted(t.name for t in listed.tools)
                check(len(names) == 4, f"tools/list returned {len(names)} tools",
                      ", ".join(names))

                result = await session.call_tool("get_stock", {"sku": "ROB007"})
                text = result.content[0].text if result.content else ""
                check("ROB007" in text, "call get_stock(ROB007)", text[:160])

                result = await session.call_tool("get_sales_for_sku", {"sku": "ROB007"})
                text = result.content[0].text if result.content else ""
                check("units_sold" in text, "call get_sales_for_sku(ROB007)", text[:160])

    print()
    if failures:
        print(f"{len(failures)} check(s) FAILED: {', '.join(failures)}")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
