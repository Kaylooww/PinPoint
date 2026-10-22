# PinPoint — Handoff

Last updated: Thursday 13:30, after the Phase D backend work.

## Done
- Phase A (backend core), steps 1–6: committed and pushed.
  - MinerU runs the **basic** tier (standard download abandoned). Both samples parse to ready.
  - Block extraction from real MinerU output; crops via `mineru read --format image` with a Pillow bbox fallback.
  - End-to-end over the API: contract penalty question and receipt invoice question answered with cited crops; the Santos question returns not_found.
- Phase D backend halves (frontend halves not started):
  - 13 Notes: GET/POST/DELETE notes, indexed and cited as kind "note" (crop_url null).
  - 14 Folders: connect, rescan, disconnect with every safety limit; plain-text files skip MinerU.
  - 15 History: history.json, GET/GET one/PATCH saved.
  - 16 Threads: /ask takes thread_id, returns thread_id + history_id.
  - 17 Knowledge: GET /knowledge.

## In progress
- Phase B (frontend core, steps 7–10): a frontend agent session is building components, Ask, Files, and the "/" redirect with mocks on. Not committed yet.

## Exact next step
- When Phase B lands: commit it, then Phase C step 11 (VITE_USE_MOCKS=false, align types.ts with the real API: AskResult adds thread_id and history_id), then step 12 (browser walkthrough).
- Then the frontend halves of Phase D items 13–18, in order.

## How to run
```sh
mineru server start          # basic tier, managed; check: mineru server status --json
cd backend && source .venv/bin/activate && uvicorn app.main:app --reload --port 8000
cd frontend && npm run dev   # http://localhost:5173
```
Tests (throwaway data dir): `cd backend && .venv/bin/python tests/test_core_fixture.py` and `.venv/bin/python tests/test_folders.py`. Add `LLM_PROVIDER=none` to test extractive mode.

## Known issues
- Start `mineru server` from a stable directory: its managed parse service writes `.mineru-service.lock` and `blobs/` into the current directory (both git-ignored).
- The organizers' server rejects `temperature` and non-strict `response_format`; llm.py sends neither.
- `backend/samples/` holds real documents and is git-ignored (the repo is public).
