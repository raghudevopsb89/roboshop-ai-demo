"""Interactive REPL for live demos -- ask anything, toggle RAG on the fly.

Commands:
    /rag        toggle RAG on/off (default: on)
    /facts      show the full retrieved chunks for the last question
    /q          list the built-in demo questions
    /quit       exit

Usage:  python3 06_chat.py
"""
import importlib
import sys

from common import CHAT_MODEL, EMBED_MODEL, chat

raw = importlib.import_module("02_ask_raw")
rag = importlib.import_module("04_ask_rag")
from questions import QUESTIONS

use_rag = True
last_hits = []

print(f"chat={CHAT_MODEL}  embed={EMBED_MODEL}")
print("commands: /rag  /facts  /q  /quit\n")

while True:
    try:
        line = input(f"[RAG {'ON ' if use_rag else 'OFF'}] > ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        break

    if not line:
        continue
    if line in ("/quit", "/exit"):
        break
    if line == "/rag":
        use_rag = not use_rag
        print(f"  RAG is now {'ON' if use_rag else 'OFF'}\n")
        continue
    if line == "/facts":
        if not last_hits:
            print("  no question asked yet\n")
        for score, src, txt in last_hits:
            print(f"  [{score:.3f}] ({src}) {txt}\n")
        continue
    if line == "/q":
        for i, item in enumerate(QUESTIONS, 1):
            print(f"  {i}. {item['q']}")
        print()
        continue
    if line.isdigit() and 1 <= int(line) <= len(QUESTIONS):
        line = QUESTIONS[int(line) - 1]["q"]
        print(f"  -> {line}\n")

    if use_rag:
        last_hits = rag.retrieve(line)
        context = "\n".join(f"- {t}" for _, _, t in last_hits)
        top = last_hits[0]
        print(f"  (top match {top[0]:.3f} from {top[1]})")
        answer = chat(f"CONTEXT:\n{context}\n\nQUESTION: {line}", system=rag.SYSTEM)
    else:
        answer = chat(line, system=raw.SYSTEM)

    print(f"\n{answer}\n")
