# Ollama + RAG
---

## Pre-requisites.

| Piece | Choice | Why |
|---|---|---|
| Runtime | Ollama 0.32.6, systemd service on `127.0.0.1:11434` | CPU-only, no GPU on this box |
| Chat model | `llama3.2:3b` (2.0 GB) | Fits comfortably in CPU RAM, ~15 s/answer |
| Embeddings | `nomic-embed-text` (274 MB), 768-dim | Runs in Ollama, so **no PyTorch install** |
| Vector store | a `rag_index` table in the same SQLite DB | 50 chunks — a real vector DB is pointless here |
| Python deps | **none** — standard library only | Avoids RHEL 10 PEP-668 `pip` friction |

```bash
dnf install zstd -y
curl -fsSL https://ollama.com/install.sh | sh
ollama list
ollama pull nomic-embed-text
ollama pull llama3.2:3b
```

Before RAG

```bash
python3 ask_raw.py 1
python3 ask_raw.py 2
```

Setup RAG

```bash
python3 setup_db.py
python3 build_index.py
```

After RAG 


```bash
python3 ask_rag.py 1
python3 ask_rag.py 2
```




