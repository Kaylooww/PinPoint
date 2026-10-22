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

## Business plan

*Problem.* Law offices, accounting firms, real estate agencies, and insurance companies handle stacks of client documents every day: scanned contracts, phone photos of receipts, PDFs, and spreadsheets. Finding one fact means opening file after file, and general AI tools can't be trusted with confidential files or blurry scans, and often guess when they don't know.

*Target users.* Staff at small and mid-sized document-heavy firms: lawyers and paralegals, bookkeepers and accountants, real estate agents, insurance staff, and the virtual assistants who support them. The firm pays, per team.

*Solution and value.* PinPoint lets you ask a plain-language question across all of a client's files at once. It reads scans and photos, finds the answer, and shows a cropped image of exactly where it came from. If the answer isn't in the files, it says so instead of guessing. Files are parsed on the firm's own computer. The result: minutes of searching become seconds, with proof attached.

*Making money.* A monthly subscription per firm (SaaS):
- *Starter* for solo professionals: 1 user, a few client workspaces.
- *Team* for small firms: up to 5 users, unlimited workspaces.
- *Firm* for larger offices: custom pricing, including on-premise installation for firms that can't use the cloud.
A 14-day free trial lets firms try it on their own files before paying.

*Competition.* General AI tools (ChatGPT, NotebookLM, Adobe Acrobat AI) work well on clean files you're allowed to upload to a big tech cloud. Enterprise platforms like Hebbia serve large finance and legal firms at enterprise prices. PinPoint is built for the firms in between: messy paperwork, strict confidentiality, and no enterprise budget. Its edge is visual proof for every answer, local parsing, and honest "not found" answers.

*Next steps (first 1–3 months).*
1. Pilot with 3–5 local firms in Cebu (law, accounting, real estate) and measure time saved per question.
2. Add automatic folder sync, team accounts with permissions, and contract version comparison.
3. Launch the paid Starter and Team plans, priced from the pilot feedback.
