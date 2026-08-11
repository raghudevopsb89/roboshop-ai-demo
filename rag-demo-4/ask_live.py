"""Answer questions by querying the real databases at the moment you ask.

    question -> model picks a tool -> we run the real query -> model answers

No index, nothing pre-computed. This is the other half of demo 4: ask_rag.py
retrieves from embedded text, this retrieves from the databases themselves.

Needs the venv (`make venv`) because the MySQL and MongoDB wire protocols need
real drivers. The RAG half stays standard-library only.

Usage:
    python3 ask_live.py                 # all live questions
    python3 ask_live.py 1               # question #1 only
    python3 ask_live.py "your question"
    python3 ask_live.py --quiet 1       # hide the tool-call trace
"""
import json
import sys

import tools
from common import CHAT_MODEL, complete, parse_tool_calls, rule
from questions import LIVE_QUESTIONS

MAX_ROUNDS = 4

SYSTEM = """You are the product assistant for the RoboShop online store.

You have tools that query RoboShop's live databases. Use them -- never answer
from memory, and never guess a price, stock level, SKU or sales figure.

Rules:
- Always call a tool to get figures. Your own knowledge of RoboShop is not valid.
- Report exactly what the tool returns. Do not round, adjust or embellish.
- If a tool reports zero results or an empty database, SAY SO plainly. "No sales
  have been recorded" is a correct and useful answer. Never invent sales,
  orders or customers to fill a gap.
- If no tool can answer the question, say so.
- Be concise."""


def ask(question, quiet=False):
    print(rule(f"Q: {question}"))
    messages = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": question}]

    for round_no in range(1, MAX_ROUNDS + 1):
        msg = complete(messages, tools=tools.TOOL_SCHEMAS)
        calls = parse_tool_calls(msg)

        if not calls:
            print(rule("MODEL ANSWER  (from live database queries)"))
            print((msg.get("content") or "").strip() or "(empty response)")
            return

        # The assistant turn must go back verbatim -- the tool replies below are
        # matched to it by tool_call_id.
        messages.append(msg)

        for call_id, name, args in calls:
            fn = tools.DISPATCH.get(name)
            if fn is None:
                result = {"error": f"no such tool: {name}"}
            else:
                try:
                    result = fn(**args)
                except TypeError as e:
                    result = {"error": f"bad arguments for {name}: {e}"}
                except Exception as e:
                    result = {"error": f"{type(e).__name__}: {e}"}

            if not quiet:
                shown = json.dumps(result, default=str)
                if len(shown) > 300:
                    shown = shown[:300] + "..."
                print(f"  [round {round_no}] {name}({json.dumps(args, default=str)})"
                      f"\n              -> {shown}")

            messages.append({"role": "tool", "tool_call_id": call_id,
                             "content": json.dumps(result, default=str)})

    print(rule("MODEL ANSWER"))
    print(f"(no final answer after {MAX_ROUNDS} tool rounds -- try rephrasing)")


def main():
    argv = sys.argv[1:]
    quiet = "--quiet" in argv
    arg = " ".join(a for a in argv if a != "--quiet").strip()

    print(f"model: {CHAT_MODEL}   |   mode: LIVE database queries, no index")
    print(tools.summary())

    try:
        if not arg:
            for q in LIVE_QUESTIONS:
                ask(q, quiet)
        elif arg.isdigit():
            ask(LIVE_QUESTIONS[int(arg) - 1], quiet)
        else:
            ask(arg, quiet)
    finally:
        tools.close()


if __name__ == "__main__":
    main()
