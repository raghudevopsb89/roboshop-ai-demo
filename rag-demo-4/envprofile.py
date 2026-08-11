"""Per-person configuration, so several people can share this repo.

Everyone has their own Foundry account (their own endpoint, key and deployment
names), so nothing about a person's setup can be committed. A profile is just a
shell-style file of the same exports `make env` prints, kept out of git:

    profiles/raghu.env
    profiles/student01.env

Select one with ROBOSHOP_PROFILE, or ignore all this and export the variables
yourself -- both work:

    ROBOSHOP_PROFILE=raghu python3 ask_rag.py 1
    source profiles/raghu.env && python3 ask_rag.py 1

Real environment variables always win over the file, so you can override a
single value for one run without editing anything:

    CHAT_MODEL=gpt-5-nano ROBOSHOP_PROFILE=raghu python3 ask_rag.py 1

Imported for its side effect by common.py and tools.py, both of which read
os.environ at import time -- so this has to land first.
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
PROFILE_DIR = os.path.join(HERE, "profiles")


def path_for(name):
    return os.path.join(PROFILE_DIR, f"{name}.env")


def available():
    if not os.path.isdir(PROFILE_DIR):
        return []
    return sorted(f[:-4] for f in os.listdir(PROFILE_DIR)
                  if f.endswith(".env") and f != "example.env")


def load(name=None):
    """Read profiles/<name>.env into os.environ without overwriting real vars."""
    name = name or os.environ.get("ROBOSHOP_PROFILE")
    if not name:
        return None

    path = path_for(name)
    if not os.path.exists(path):
        known = ", ".join(available()) or "(none yet)"
        raise SystemExit(
            f"no such profile: {path}\n"
            f"available: {known}\n\n"
            f"Create one from your own Foundry stack:\n"
            f"  cd ../infra && ENV={name} make profile")

    with open(path) as f:
        for raw in f:
            stmt = raw.strip()
            if not stmt or stmt.startswith("#"):
                continue
            if stmt.startswith("export "):
                stmt = stmt[len("export "):]
            if "=" not in stmt:
                continue
            key, value = stmt.split("=", 1)
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            # setdefault, not assignment: an explicit env var beats the file.
            os.environ.setdefault(key.strip(), value)
    return name


ACTIVE = load()
