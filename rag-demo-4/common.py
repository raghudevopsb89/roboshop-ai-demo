"""Shared helpers: a tiny Microsoft Foundry client and cosine similarity.

Same shape as rag-demo-2/common.py, pointed at a hosted endpoint instead of
local Ollama. Still pure standard library -- the OpenAI-compatible /openai/v1/
route is plain HTTPS + JSON, so no `pip install openai` is needed and the RHEL
10 PEP-668 friction stays avoided.

Three differences from the Ollama client worth pointing at during the demo:

1. AUTH. Every request carries an Authorization: Bearer header. Ollama on
   localhost needed none.

2. RESPONSE SHAPE. Chat replies arrive as choices[0].message.content, not
   message.content. Embeddings arrive as a `data` list of objects carrying an
   `index`, not a bare `embeddings` list -- and the list is NOT guaranteed to
   come back in request order, so embed() sorts by index. Getting that wrong
   silently pairs the wrong vector with the wrong chunk, which produces an
   index that looks fine and retrieves nonsense.

3. FAILURE MODES. A local model either works or the socket is closed. A hosted
   one returns 401, 404 and 429, so _post() surfaces the server's own error
   text and retries throttling with backoff.
"""
import json
import math
import os
import time
import urllib.error
import urllib.request

# Imported for its side effect: if ROBOSHOP_PROFILE is set, it loads
# profiles/<name>.env into os.environ before anything below reads it. Everyone
# has their own Foundry, so none of these values can be committed.
import envprofile  # noqa: F401

# From `make env` in ../infra -- e.g. https://<name>.openai.azure.com/openai/v1
AZURE_BASE = os.environ.get("AZURE_BASE", "").rstrip("/")
AZURE_KEY = os.environ.get("AZURE_KEY", "")

# These are DEPLOYMENT names from the Terraform, not model names. They only
# match the model names because infra/env-dev/main.tfvars names them alike.
CHAT_MODEL = os.environ.get("CHAT_MODEL", "gpt-5-mini")
EMBED_MODEL = os.environ.get("EMBED_MODEL", "text-embedding-3-small")

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(HERE, "roboshop.db")

# Hosted endpoints throttle. A RAG turn carries five retrieved chunks of
# context, and a tool-calling turn is several round trips, so 429 is a normal
# operating condition rather than an error -- the retry budget is deliberately
# generous and _post() honours Retry-After. Lower deployment capacity in
# infra/ makes this more likely, not less.
MAX_RETRIES = int(os.environ.get("MAX_RETRIES", "6"))


def require_config():
    """Fail early and actionably rather than with a confusing 401 later."""
    missing = [n for n in ("AZURE_BASE", "AZURE_KEY") if not globals()[n]]
    if missing:
        known = envprofile.available()
        if envprofile.ACTIVE:
            hint = (f"Profile '{envprofile.ACTIVE}' is loaded but does not set "
                    f"{' / '.join(missing)}.\n"
                    f"  {envprofile.path_for(envprofile.ACTIVE)}")
        elif known:
            hint = ("Select one of your profiles:\n"
                    f"  export ROBOSHOP_PROFILE={known[0]}"
                    f"        (available: {', '.join(known)})")
        else:
            hint = ("Either export them directly:\n"
                    "  cd ../infra && eval \"$(ENV=<yourname> make -s env)\"\n"
                    "or save them once as a profile:\n"
                    "  cd ../infra && ENV=<yourname> make profile\n"
                    "  export ROBOSHOP_PROFILE=<yourname>")
        raise SystemExit(
            "missing environment variable(s): " + ", ".join(missing) + "\n\n" + hint)


def _describe(code, detail):
    hint = ""
    if code == 401:
        hint = "\nAZURE_KEY is wrong or expired -- re-run: eval \"$(make -s env)\""
    elif code == 404:
        hint = ("\nNo deployment named that on this endpoint. Check with:"
                "\n  az cognitiveservices account deployment list "
                "-g <rg> -n <account> -o table")
    return f"HTTP {code}: {detail}{hint}"


def _post(path, payload, timeout=120, soft=False):
    """POST and return the decoded body.

    soft=True returns {"__error__": {...}} on a non-retryable HTTP error
    instead of exiting, so the caller can adapt. Used by chat() to recover from
    models that reject parameters other models accept.
    """
    require_config()
    body = json.dumps(payload).encode()

    for attempt in range(MAX_RETRIES):
        req = urllib.request.Request(
            AZURE_BASE + path,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {AZURE_KEY}",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")[:400]
            # 429 is the one to expect. Azure returns a Retry-After header
            # saying how long the window actually has left -- honour it rather
            # than guessing, because plain exponential backoff will happily
            # retry three times inside a 60-second window and still fail.
            if e.code in (429, 500, 502, 503, 504) and attempt < MAX_RETRIES - 1:
                try:
                    wait = int(e.headers.get("Retry-After", ""))
                except (TypeError, ValueError):
                    wait = 2 ** attempt
                print(f"  [{e.code}] retrying in {wait}s ...")
                time.sleep(wait)
                continue
            if soft:
                return {"__error__": {"code": e.code, "detail": detail}}
            raise SystemExit(f"{path} -> {_describe(e.code, detail)}")
        except urllib.error.URLError as e:
            raise SystemExit(f"cannot reach {AZURE_BASE}: {e}")

    raise SystemExit(f"{path} still failing after {MAX_RETRIES} attempts")


# Set to False once a model tells us it won't take a temperature, so we stop
# sending one for the rest of the run.
_TEMPERATURE_OK = True


def complete(messages, tools=None, temperature=0.0):
    """One /chat/completions round trip. Returns the assistant message dict.

    temperature=0 is what keeps demos 1-3 reproducible, and most models honour
    it. The GPT-5 family does NOT: it accepts only its default and returns 400
    "does not support 0 with this model" for anything else. Rather than
    hardcode which is which -- a list that would rot -- send it, and drop it
    permanently for the run if the model objects.

    Pass `tools` to let the model call functions instead of answering; the reply
    then carries `tool_calls` and an empty `content`. See ask_live.py.
    """
    global _TEMPERATURE_OK

    payload = {"model": CHAT_MODEL, "messages": messages}
    if tools:
        payload["tools"] = tools
    if _TEMPERATURE_OK:
        payload["temperature"] = temperature

    out = _post("/chat/completions", payload, soft=True)
    err = out.get("__error__")
    if err:
        if err["code"] == 400 and "temperature" in err["detail"].lower():
            _TEMPERATURE_OK = False
            payload.pop("temperature", None)
            print(f"  note: {CHAT_MODEL} rejects an explicit temperature; "
                  f"using its default (answers will vary slightly between runs)")
            out = _post("/chat/completions", payload)
        else:
            raise SystemExit(
                f"/chat/completions -> {_describe(err['code'], err['detail'])}")

    return out["choices"][0]["message"]


def chat(prompt, system=None, temperature=0.0):
    """Single-turn chat completion, returning just the text."""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    msg = complete(messages, temperature=temperature)
    return (msg.get("content") or "").strip()


def parse_tool_calls(message):
    """Normalise tool_calls into [(call_id, name, args_dict), ...].

    The OpenAI-compatible route returns `arguments` as a JSON *string* (Ollama
    returns a dict), and each call carries an `id` that the matching tool reply
    must quote back as `tool_call_id` -- omit it and the next request 400s.
    """
    out = []
    for call in message.get("tool_calls") or []:
        fn = call.get("function") or {}
        args = fn.get("arguments")
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                args = {}
        out.append((call.get("id"), fn.get("name"), args or {}))
    return out


def embed(texts):
    """Embed a list of strings -> list of vectors, in the order given."""
    out = _post("/embeddings", {"model": EMBED_MODEL, "input": texts})
    # Sort by index: the API does not promise to echo the input order back.
    rows = sorted(out["data"], key=lambda d: d["index"])
    return [r["embedding"] for r in rows]


def cosine(a, b):
    """Kept in full form for readability.

    Azure's text-embedding-3-* vectors are already L2-normalised, so this is
    mathematically just a dot product here -- but the general form still works
    if you point EMBED_MODEL at something that isn't normalised.
    """
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def rule(title=""):
    line = "=" * 78
    return f"\n{line}\n{title}\n{line}" if title else f"\n{line}"
