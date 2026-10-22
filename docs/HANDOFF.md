# PinPoint — Handoff

Last updated: Thursday 13:50, after Phase D items 15–16 (history, saved, follow-ups).

## Done (and tested)
- Phase A 1–6: backend core on MinerU **basic** tier; both samples parse to ready; crops; API end-to-end.
- Phase B 7–10: components, Ask + citation panel, Files + folder upload, "/" → /w/reyes-partners/ask.
- Phase C 11–12: mocks off (frontend/.env.local VITE_USE_MOCKS=false); ask() returns AskResult. Browser walkthrough against the real backend passed: upload → parsing → ready → cited answer → crops load → panel → Escape → dark mode → not-found → answer from an uploaded .md (text card, no crop). No console errors or external requests.
- Phase D 13 Notes: done end to end (Memory tab add/delete, note citation cards, panel). Browser-tested against the real backend in light and dark.
- Phase D 14 Folders: done end to end (Add files → Connect a local folder dialog, Connected folders section, Rescan, Disconnect, Folder tag). Browser-tested with a 3-file folder; folder untouched on disk.
- Phase D 15–16: done end to end. Ask is a thread (Save per answer, Ask a follow-up keeps thread_id, New question resets), recent questions from GET /history, ?h=<id> reopens a past answer without re-asking; Memory tab has Saved answers and History grouped by day. Browser-tested in light and dark.
- Phase D backend half (tests pass): 17 knowledge.

## In progress
- Phase D frontend halves, in order 13 → 18.

## Exact next step
- 17 stats strip under the workspace title on Files (GET /knowledge): "6 files · 41 pages · 312 passages indexed · 2 notes · Updated 2 min ago". Then 18 workspaces grid + New workspace dialog, static Sign in and Landing, "/" → Landing.

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
