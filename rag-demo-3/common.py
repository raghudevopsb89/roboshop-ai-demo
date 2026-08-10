"""Tiny Ollama client, this time with tool-calling support.

Demos 1 and 2 only ever needed a single-turn completion. Tool calling is a loop:

    user question
      -> model replies with tool_calls instead of prose
      -> we execute the tools for real
      -> results go back as role="tool" messages
      -> model replies again, now with the data

Ollama returns tool call arguments as a dict, unlike the OpenAI API which returns
a JSON string. parse_tool_calls() below accepts either.
"""
import json
import urllib.error
import urllib.request

from config import CHAT_MODEL, OLLAMA


def _post(path, payload, timeout=600):
    req = urllib.request.Request(
        OLLAMA + path,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.URLError as e:
        raise SystemExit(
            f"cannot reach Ollama at {OLLAMA}: {e}\n"
            "Is the service up?  systemctl status ollama")


def chat(messages, tools=None, temperature=0.0):
    """One round trip. Returns the raw assistant message dict."""
    payload = {
        "model": CHAT_MODEL,
        "messages": messages,
        "stream": False,
        "options": {"temperature": temperature},
    }
    if tools:
        payload["tools"] = tools
    return _post("/api/chat", payload)["message"]


def parse_tool_calls(message):
    """Normalise Ollama's tool_calls into [(name, args_dict), ...]."""
    out = []
    for call in message.get("tool_calls") or []:
        fn = call.get("function") or {}
        name = fn.get("name")
        args = fn.get("arguments")
        if isinstance(args, str):          # OpenAI-style JSON string
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                args = {}
        out.append((name, args or {}))
    return out


def rule(title=""):
    line = "=" * 78
    return f"\n{line}\n{title}\n{line}" if title else f"\n{line}"
