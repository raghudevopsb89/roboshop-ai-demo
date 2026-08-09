"""Shared helpers: a tiny Ollama client and cosine similarity.

Deliberately pure standard library -- no pip installs required.
Identical in spirit to rag-demo-1/common.py; only the database name differs.
"""
import json
import math
import os
import urllib.request

OLLAMA = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
CHAT_MODEL = os.environ.get("CHAT_MODEL", "llama3.2:3b")
EMBED_MODEL = os.environ.get("EMBED_MODEL", "nomic-embed-text")

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(HERE, "roboshop.db")

# The real monorepo whose SQL files this demo indexes. Override if it moves.
AZURE_REPO = os.environ.get(
    "AZURE_REPO", "/Users/skalluru/repos/cit/d89/azure-services"
)


def _post(path, payload, timeout=600):
    req = urllib.request.Request(
        OLLAMA + path,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def chat(prompt, system=None, temperature=0.0):
    """Single-turn chat completion. temperature=0 keeps the demo reproducible."""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    out = _post("/api/chat", {
        "model": CHAT_MODEL,
        "messages": messages,
        "stream": False,
        "options": {"temperature": temperature},
    })
    return out["message"]["content"].strip()


def embed(texts):
    """Embed a list of strings -> list of vectors."""
    out = _post("/api/embed", {"model": EMBED_MODEL, "input": texts})
    return out["embeddings"]


def cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def rule(title=""):
    line = "=" * 78
    return f"\n{line}\n{title}\n{line}" if title else f"\n{line}"
