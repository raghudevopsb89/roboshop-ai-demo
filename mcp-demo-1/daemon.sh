#!/usr/bin/env bash
# Run the MCP server detached, so it survives the shell that started it.
#
# `make run-sqlite` holds the terminal, which is right for a demo you are
# watching but wrong for a box you SSH into and then disconnect from.
#
#   ./daemon.sh start     stop any old instance, then start detached
#   ./daemon.sh stop
#   ./daemon.sh status
#   ./daemon.sh log       follow the log
#
# Environment (all optional):
#   MCP_TOKEN          bearer token; generated and saved to .mcp_token if unset
#   MCP_PUBLIC_HOST    address clients dial, e.g. a VM's public IP
#   MCP_PORT           default 8080
#   ROBOSHOP_BACKEND   sqlite (default here) or live
set -u

# readlink -f is GNU-only, so resolve the script's directory portably.
cd "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)" || exit 1

PY="./.venv/bin/python"
LOG="./mcp.log"
TOKEN_FILE="./.mcp_token"
# Matches the real python process only. Note this script exists as a FILE for a
# reason: running the same pkill inline over ssh matches the wrapper shell's own
# command line and kills the session before it can start anything.
PATTERN='python.*server\.py'

: "${ROBOSHOP_BACKEND:=sqlite}"
export ROBOSHOP_BACKEND
export MCP_BIND_HOST="${MCP_BIND_HOST:-0.0.0.0}"

die() { echo "$*" >&2; exit 1; }

ensure_token() {
    if [ -n "${MCP_TOKEN:-}" ]; then return; fi
    if [ -s "$TOKEN_FILE" ]; then
        MCP_TOKEN="$(cat "$TOKEN_FILE")"
    else
        MCP_TOKEN="$("$PY" -c 'import secrets;print(secrets.token_hex(32))')" \
            || die "could not generate a token"
        umask 077; printf '%s\n' "$MCP_TOKEN" > "$TOKEN_FILE"
        echo "generated a new token -> $TOKEN_FILE"
    fi
    export MCP_TOKEN
}

case "${1:-start}" in
start)
    [ -x "$PY" ] || die "no venv here -- run: make venv"
    pkill -f "$PATTERN" 2>/dev/null && sleep 2
    ensure_token
    if [ "$ROBOSHOP_BACKEND" = "sqlite" ] && [ ! -f ./roboshop.db ]; then
        "$PY" setup_db.py > /dev/null || die "setup_db.py failed"
    fi
    # Closed stdin + redirected output + a new session = survives this shell
    # exiting. setsid is util-linux, so it is missing on macOS; nohup plus
    # disown is the portable fallback and is enough to outlive the shell.
    if command -v setsid > /dev/null 2>&1; then
        setsid "$PY" server.py < /dev/null > "$LOG" 2>&1 &
    else
        nohup "$PY" server.py < /dev/null > "$LOG" 2>&1 &
        disown 2> /dev/null || true
    fi
    sleep 5
    pid="$(pgrep -f "$PATTERN" | head -1)"
    [ -n "$pid" ] || { echo "FAILED to start:"; tail -15 "$LOG"; exit 1; }
    echo "started pid $pid (ppid $(ps -o ppid= -p "$pid" | tr -d ' '))"
    grep -E "backend :|endpoint|url  " "$LOG" | sed 's/^/  /'
    echo "  token: $TOKEN_FILE"
    ;;
stop)
    if pkill -f "$PATTERN" 2>/dev/null; then sleep 2; echo "stopped"; else echo "not running"; fi
    ;;
status)
    pid="$(pgrep -f "$PATTERN" | head -1)"
    if [ -n "$pid" ]; then
        echo "running pid $pid (ppid $(ps -o ppid= -p "$pid" | tr -d ' '), up $(ps -o etime= -p "$pid" | tr -d ' '))"
    else
        echo "not running"; exit 1
    fi
    ;;
log)
    tail -f "$LOG"
    ;;
*)
    die "usage: $0 {start|stop|status|log}"
    ;;
esac
