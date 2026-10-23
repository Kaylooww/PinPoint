# PinPoint

*Ask your documents anything. See exactly where the answer came from.*

PinPoint lets you ask a plain-language question across a workspace of PDFs, scans, photos, and spreadsheets. It returns the answer with a cropped snapshot of the exact spot in the source file, so you can check it at a glance.

Built for the ALMA *Future Forge* hackathon.

| | |
|---|---|
| 🎬 *Demo video* | [Watch on YouTube](https://www.youtube.com/watch?v=1GbLXRP_tac) |
| 🖼️ *Slides* | [View the pitch deck on Canva](https://www.canva.com/design/DAHYtrBfgA0/lPM_WvFC0Cx35VP6MiyrZg/edit) |
| 🛠️ *Developer docs* | [AGENTS.md](AGENTS.md) and [docs/](docs/) |

---

## Team

| Name |
|---|
| Kyle Angelo C. Castro |
| Luther Derrick E. Dira |
| Jon Vincent F. Din |
| Zyril Reyes R. Restauro |

---

## Problem

*Businesses don't lack information. They lose time finding it.*

About *25% of the workday* goes to searching for answers (Atlassian, State of Teams 2025). Document-heavy firms feel this most: law offices, accounting firms, real estate agencies, and insurance companies.

- *Scattered formats.* Answers are buried in photos, scans, PDFs, spreadsheets, and decks.
- *Search falls short.* Ctrl+F can't read a scanned contract and doesn't understand meaning.
- *One file at a time.* A single answer can mean opening a dozen files.
- *AI you can't trust.* General AI tools guess when they don't know, so staff still double-check the originals. Many firms also can't upload confidential client files to a public cloud.

*A client's filing deadline is on page 30 of a scanned contract, in a folder of 40 files. How long would it take you to find it?*


---

## MVP Solution

PinPoint answers questions across *every file in a workspace at once* and attaches proof to every answer.

| | What it means |
|---|---|
| *Every file at once* | Photos, scans, PDFs, and spreadsheets are all searched with one question. |
| *Visual proof* | Every answer shows a cropped snapshot of the exact source, with the file name and page. |
| *No guessing* | If the answer isn't in your files, PinPoint says *"Not found"* instead of making one up. |
| *Private by design* | Files are parsed locally on the firm's own machine. The AI runs on ALMA's servers. |

*Example*

**Q:** When is this client's filing deadline?
**A:** March 14, 2027. *(Contract_Scan.pdf, p. 30, with the highlighted clause shown)*


---

## How it works

*Upload* → *Parse locally* → *Ask* → *Search* → *Answer with proof*

*1. Upload*
Add any mix of files to a workspace: photos, scans, PDFs, spreadsheets, Word documents, slides, and more.

↓

*2. Parse locally*
MinerU reads every file on the laptop, including OCR for scans and photos, page layout, and tables. Nothing is uploaded for parsing.

↓

*3. Ask*
Type a question in plain language, such as "When is this client's filing deadline?"

↓

*4. Search*
PinPoint searches every file at once, combining keyword matching (BM25) with search by meaning (embeddings).

↓

*5. Answer with proof*
Claude Haiku writes the answer from the matching passages. PinPoint attaches a cropped snapshot of the exact source, with the file name and page. If nothing matches, you get *"Not found"* instead of a guess.

*Built to keep working.* If the LLM errors or times out, PinPoint automatically falls back to extractive mode and shows the best-matching passages. It can also run with no LLM at all.

---

## Tech stack

| Layer | Technology |
|---|---|
| *Frontend* | React 19, TypeScript, Vite, Tailwind CSS 4, React Router, Lucide icons. Fonts (Inter, Instrument Serif) are bundled locally, so the app loads nothing from the internet. |
| *Backend* | Python 3.12 with FastAPI and Uvicorn |
| *Document parsing* | [MinerU](https://github.com/opendatalab/MinerU) 4, an open-source parser that runs locally on the laptop (OCR, layout, and table extraction) |
| *Search* | Hybrid search: BM25 keyword search (rank_bm25) combined with embedding search from the organizers' embedding server |
| *AI model* | Claude Haiku (claude-haiku-5-5), served through the organizers' Open WebUI server with an OpenAI-compatible API |
| *Image crops* | MinerU's page rendering, with Pillow as a fallback |
| *Storage* | Plain JSON files and folders on disk, no database. This keeps everything local and easy to inspect. |

All LLM calls go through a single module, backend/app/llm.py. If the model is unavailable, PinPoint falls back to the Anthropic API or to extractive mode (no LLM).

---

## Business plan

### Target market
Small and mid-sized *document-heavy firms*: lawyers and paralegals, bookkeepers and accountants, real estate agents, insurance staff, and the virtual assistants who support them. The firm pays, per workspace.

| Industry | A typical question |
|---|---|
| Law offices | "When is the filing deadline?" |
| Accounting & bookkeeping | "What's the total on last month's invoices?" |
| Real estate | "What's the lease renewal clause?" |
| Insurance | "Is flood damage excluded?" |

The global intelligent document processing market is about *USD 3.3B in 2025* and growing *over 30% per year* (IMARC Group, Intelligent Document Processing Market Report 2026–2034).

### Value
- *Faster:* questions that took minutes take seconds.
- *Trustworthy:* every answer comes with visual proof, with no guessing.
- *Private:* documents are parsed locally, and the AI runs on ALMA's own servers.

*More hours on client work. Fewer hours hunting through files.*

### Revenue model: simple subscription, priced per workspace

| Plan | Price | For | Includes |
|---|---|---|---|
| *Free* | PHP 0 | Students and trial users | 1 workspace, limited files |
| *Pro* | PHP 999 / month | Solo professionals | Unlimited questions |
| *Team* | PHP 4,999 / month | Small firms of up to 10 users | Shared and per-client workspaces |
| *Enterprise* | Custom pricing | Larger offices | On-premise deployment, folder sync, permissions |

*Additional revenue streams*
- *Enterprise onboarding fee:* one-time implementation support.
- *Exports add-on:* charged per export request.

### Path to growth
A three-year projection of annual recurring revenue, at a blended *PHP 4,000 per firm per month*:

| Year | Paying firms | ARR | Product focus |
|---|---|---|---|
| Year 1 | 50 | *PHP 2.4M* | Folder sync, per-client workspaces |
| Year 2 | 250 | *PHP 12M* | Cross-document comparisons, exports |
| Year 3 | 800 | *PHP 38.4M* | Team access and permissions for larger firms |

Projections are internal team estimates based on our proposed pricing, not external market data.

### Next steps (first 1–3 months)
1. Pilot with 3–5 local firms in Cebu (law, accounting, real estate) and measure the time saved per question.
2. Add automatic folder sync, team accounts with permissions, and contract version comparison.
3. Launch the paid Pro and Team plans, with pricing tuned from pilot feedback.

---

## Demo video

▶️ *[Watch the PinPoint demo on YouTube](https://www.youtube.com/watch?v=1GbLXRP_tac)*

## Slides

🖼️ *[View the PinPoint pitch deck on Canva](https://www.canva.com/design/DAHYtrBfgA0/lPM_WvFC0Cx35VP6MiyrZg/edit)*

---

## Running PinPoint locally

<details>
<summary><strong>1. MinerU (local document parsing)</strong></summary>

MinerU runs as a command-line tool with its own local server, separate from the backend venv. All parsing stays on this machine; never use --remote.

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
</details>

<details>
<summary><strong>2. Backend (Python 3.12)</strong></summary>

cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env    # then fill in the LLM settings below (never commit .env)

### Local models (Ollama)

PinPoint runs on free local models through [Ollama](https://ollama.com) (0.20 or newer). Nothing leaves the laptop.

```sh
brew install ollama             # or the macOS app from ollama.com; then start it (ollama serve, or open the app)
ollama pull gemma4:e2b          # chat model, ~7.5 GB
ollama pull embeddinggemma      # embedding model, ~620 MB (nomic-embed-text also works)
```

In `backend/.env`:

```sh
LLM_PROVIDER=openai_compatible
OPENAI_COMPAT_BASE=http://localhost:11434/v1
OPENAI_COMPAT_KEY=ollama
OPENAI_COMPAT_MODEL=gemma4:e2b
EMBED_BASE=http://localhost:11434/v1
EMBED_KEY=ollama
EMBED_MODEL=embeddinggemma
EMBED_DIMENSIONS=768
LLM_TIMEOUT_SECONDS=120
EMBED_TIMEOUT_SECONDS=15
```

Switching embedding models needs no re-upload: on the next start, each workspace is re-embedded in the background from its saved blocks (a few minutes for ~17k passages); search uses keywords alone until it finishes.

### LLM provider

| LLM_PROVIDER | What it uses | Settings |
|---|---|---|
| `openai_compatible` (primary) | Local Ollama (`gemma4:e2b`), or any OpenAI-compatible server | `OPENAI_COMPAT_BASE` (Ollama: `http://localhost:11434/v1`), `OPENAI_COMPAT_KEY`, `OPENAI_COMPAT_MODEL` |
| `anthropic` (optional, cloud) | Claude Haiku via the Anthropic API | `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` (default `claude-haiku-5-5`) |
| `none` (fallback) | No LLM: extractive mode shows the best-matching passages | none; the app makes no outbound calls |

If the LLM errors or times out (`LLM_TIMEOUT_SECONDS`, default 45; use 120 locally), answers fall back to extractive mode automatically. With a local server, thinking is off for speed; set `LLM_REASONING_EFFORT=low` to turn it on (more accurate on some questions, 4–10× slower).

**Getting an Anthropic API key (optional cloud provider only):** sign in at [platform.claude.com](https://platform.claude.com), add billing under Settings → Billing, then create a key under Settings → API keys and paste it into `ANTHROPIC_API_KEY` in `backend/.env`. A Claude Pro or Max subscription does not include API access.

<details>
<summary><strong>3. Frontend</strong></summary>

cd frontend
npm install
cp .env.example .env.local    # VITE_USE_MOCKS=true runs without the backend
</details>

### Start order

mineru server start
cd backend && source .venv/bin/activate && uvicorn app.main:app --reload --port 8000
cd frontend && npm run dev    # http://localhost:5173
```

`GET http://localhost:8000/api/health` reports the LLM, the embedding model, and MinerU server status. Restart the backend after editing `backend/.env`.

GET http://localhost:8000/api/health reports the LLM provider and MinerU server status. Restart the backend after editing backend/.env.
