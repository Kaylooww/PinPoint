# PinPoint — Remaining Plan (source of truth for any agent session)

Read AGENTS.md, this file, docs/TASKS.md, and docs/HANDOFF.md before doing anything. Work through the phases in order. Commit and push after every step, and update docs/HANDOFF.md after every step (what's done, what's in progress, the exact next step, how to run things, known bugs).

## Timeline (Thursday)
- Until about 2:45 PM: Phases A–C (core plus integration)
- 2:45–4:00 PM: Phase D (extras). The team works on slides from 3:30; the agent keeps building.
- 4:00 PM: Phase E (demo prep). 4:15 PM: code freeze. 5:00 PM: deadline.

## Phase A — Backend core
1. Commit all uncommitted backend work (never stage .env).
2. Fix the BM25 IDF bug: an always-positive IDF (Lucene-style log(1 + (N - n + 0.5) / (n + 0.5)), or BM25Plus). Re-run the fixture test until it passes.
3. MinerU basic tier: mineru-kit models verify --tier basic; mineru config set parse_server.local.managed_tier basic; mineru config set parse_server.local.mode managed; mineru server restart; poll mineru server status --json until healthy. Parse both files in backend/samples/ with --tier basic --pages all --json, and save the .mineru.json outputs.
4. Block extraction in backend/app/parsing.py from the real JSON. Upload both samples into Reyes & Partners through the API, and confirm both reach "ready".
5. Crops: mineru read "<locator>" --format image, with a Pillow bbox fallback. Serve at /api/crops/{id}.png.
6. End-to-end test: one question per sample plus one with no answer.

## Phase B — Frontend core (mocks on)
7. Components from Figma 3:2: Button, Field, SearchInput, StatusBadge, FileRow, WorkspaceCard, CitationCard, AnswerCard, CitationPanel.
8. Ask screen (Figma 7:542 and 7:748): question input, loading skeleton, answer with numbered citation markers, citation crop cards, side panel on click, not-found state.
9. Files screen (Figma 6:435): drag-and-drop upload; "Upload a folder" (showDirectoryPicker with a webkitdirectory fallback; supported extensions only; batches of 10); file list with status badges; polling while files are parsing.
10. Temporarily redirect "/" to /w/reyes-partners/ask.

## Phase C — Integration
11. Set VITE_USE_MOCKS=false. Fix any mismatches between types.ts and the real API (update docs/ARCHITECTURE.md if the contract changes).
12. Walk the full flow in the browser and fix every bug: upload → queued, parsing, ready → ask → cited answer → crops load → citation panel → not-found question → dark mode. If the LLM fails, the extractive fallback must appear, not a crash. Report each step as pass or fail.

## Phase D — Extras (vertical slices: backend + frontend + test + commit, one at a time; stop at 4:00 PM)
13. Notes (memory): endpoints, indexing as kind "note", Memory tab add and delete, note citation cards. (May already be partly done; check first.)
14. Connect a local folder: folder endpoints with every safety limit in docs/ARCHITECTURE.md; Files tab dialog, connected folders section, Rescan, Disconnect.
15. History and saved answers: history.json, GET and PATCH endpoints, Save button, Memory tab sections, recent questions from the history API.
16. Follow-up threads: thread_id on /ask; "Ask a follow-up" and "New question" in the UI.
17. Knowledge stats strip on the Files tab.
18. Workspaces grid plus a New workspace dialog; static Sign in and Landing pages from Figma; point "/" to Landing.

## Phase E — Demo prep (at 4:00 PM, no new features)
19. backend/scripts/reset_demo.py: rebuilds "Reyes & Partners" from backend/demo_files/ and waits until all files are ready.
20. Pre-warm the answer cache with the demo questions in docs/DEMO_QUESTIONS.md (the team will write that file).
21. Run the full demo flow once more, in light and dark mode. Fix only real bugs.
22. docs/DEMO.md: start commands, pre-demo checklist (venue Wi-Fi, MinerU healthy, /api/health ok, cache warmed), click-by-click script, fallback plan.
23. Commit, push, and tag demo-final.
