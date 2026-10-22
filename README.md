# PinPoint

Ask a plain-language question across a workspace's PDFs, scans, photos, and spreadsheets, and get the answer with a cropped snapshot of exactly where it came from.

Built for the ALMA "Future Forge" hackathon. Start with [AGENTS.md](AGENTS.md) and the docs in [docs/](docs/).

## 1. MinerU (local document parsing)

MinerU runs as a command-line tool with its own local server, separate from the backend venv. All parsing stays on this machine; never use `--remote`.

```sh
brew install uv                                   # or: pip install uv
uv tool install --python 3.12 "mineru>=4.0,<5"
uv tool update-shell                              # puts ~/.local/bin on PATH; restart the terminal
mineru version --json

mineru server start
mineru telemetry disable                          # no outbound calls at runtime (needs the server running)

mineru-kit models download --tier basic           # the tier PinPoint is tested with (~900 MB)
mineru-kit models verify --tier basic
mineru config set parse_server.local.managed_tier basic
mineru config set parse_server.local.mode managed
mineru server restart
mineru server status --json                       # wait until the tier is healthy
```

## 2. Backend (Python 3.12)

```sh
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env    # then fill in the LLM settings below (never commit .env)
```

### LLM provider

Set `LLM_PROVIDER` in `backend/.env`. Only `backend/app/llm.py` talks to an LLM.

| `LLM_PROVIDER` | What it uses | Settings |
|---|---|---|
| `openai_compatible` (primary) | Claude Haiku via the organizers' Open WebUI server (model `claude-haiku-5-5`) | `OPENAI_COMPAT_BASE` (for Open WebUI usually `https://<host>/api`), `OPENAI_COMPAT_KEY`, `OPENAI_COMPAT_MODEL` |
| `anthropic` (fallback) | Claude Haiku via the Anthropic API | `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` (default `claude-haiku-5-5`) |
| `none` (fallback) | No LLM: extractive mode shows the best-matching passages | none; the app makes no outbound calls |

If the LLM errors or times out (`LLM_TIMEOUT_SECONDS`, default 45), answers fall back to extractive mode automatically.

**Getting an Anthropic API key (fallback only):** sign in at [platform.claude.com](https://platform.claude.com), add billing under Settings → Billing, then create a key under Settings → API keys and paste it into `ANTHROPIC_API_KEY` in `backend/.env`. A Claude Pro or Max subscription does not include API access.

## 3. Frontend

```sh
cd frontend
npm install
cp .env.example .env.local    # VITE_USE_MOCKS=true runs without the backend
```

## Start order

```sh
mineru server start
cd backend && source .venv/bin/activate && uvicorn app.main:app --reload --port 8000
cd frontend && npm run dev    # http://localhost:5173
```

`GET http://localhost:8000/api/health` reports the LLM provider and MinerU server status. Restart the backend after editing `backend/.env`.
