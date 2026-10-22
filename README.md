# PinPoint

Ask a plain-language question across a workspace's PDFs, scans, photos, and spreadsheets, and get the answer with a cropped snapshot of exactly where it came from.

Built for the ALMA "Future Forge" hackathon. Start with [AGENTS.md](AGENTS.md) and the docs in [docs/](docs/).

## Setup

Backend (Python 3.12):

```sh
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in the Gemma values
uvicorn app.main:app --reload --port 8000
```

Frontend:

```sh
cd frontend
npm install
cp .env.example .env.local
npm run dev            # http://localhost:5173
```

MinerU 4.x must be installed locally for parsing (`mineru version --json`).
