# PinPoint — Handoff

Last updated: Thursday 13:45, after Phase D item 14 (folders).

## Done (and tested)
- Phase A 1–6: backend core on MinerU **basic** tier; both samples parse to ready; crops; API end-to-end.
- Phase B 7–10: components, Ask + citation panel, Files + folder upload, "/" → /w/reyes-partners/ask.
- Phase C 11–12: mocks off (frontend/.env.local VITE_USE_MOCKS=false); ask() returns AskResult. Browser walkthrough against the real backend passed: upload → parsing → ready → cited answer → crops load → panel → Escape → dark mode → not-found → answer from an uploaded .md (text card, no crop). No console errors or external requests.
- Phase D 13 Notes: done end to end (Memory tab add/delete, note citation cards, panel). Browser-tested against the real backend in light and dark.
- Phase D 14 Folders: done end to end (Add files → Connect a local folder dialog, Connected folders section, Rescan, Disconnect, Folder tag). Browser-tested with a 3-file folder; folder untouched on disk.
- Phase D backend halves (tests pass): 15 history, 16 threads, 17 knowledge.

## In progress
- Phase D frontend halves, in order 13 → 18.

## Exact next step
- 15 history UI: Save button on the answer card (PATCH history), Memory tab Saved answers + History (grouped by day, status badge, click reopens the full answer), Ask recent questions from GET /history instead of localStorage. Then 16 follow-ups, 17 stats strip, 18 workspaces/sign-in/landing.

## How to run
```sh
mineru server start          # basic tier, managed; check: mineru server status --json
cd backend && source .venv/bin/activate && uvicorn app.main:app --reload --port 8000
cd frontend && npm run dev   # http://localhost:5173
```
Tests (throwaway data dir): `cd backend && .venv/bin/python tests/test_core_fixture.py` and `.venv/bin/python tests/test_folders.py`. Add `LLM_PROVIDER=none` to test extractive mode.

## Known issues
- Figma MCP (claude.ai connector) disconnected at 13:35; new screens reuse existing components until it is re-authenticated.
- Browser walkthrough driver (CDP, no deps) lives in the agent scratchpad, not the repo.
- Start `mineru server` from a stable directory: its managed parse service writes `.mineru-service.lock` and `blobs/` into the current directory (both git-ignored).
- The organizers' server rejects `temperature` and non-strict `response_format`; llm.py sends neither.
- `backend/samples/` holds real documents and is git-ignored (the repo is public).
