# PinPoint — Agent Guide

Before any task, read this file, then docs/PRODUCT.md, docs/ARCHITECTURE.md, and docs/DESIGN.md. Tick items in docs/TASKS.md as you finish them.

## Context
- PinPoint is a document-based RAG web app for a 4-hour hackathon (ALMA "Future Forge"). Judges score a working live demo and the presentation at 70% combined, so reliability beats feature count.
- MVP only. Payments, real authentication, team invites, and sharing are out of scope. Their UI may exist as static screens but must not call anything.

## Stack
- frontend/: React + Vite + TypeScript (strict) + Tailwind CSS + react-router-dom + lucide-react. Fonts self-hosted via @fontsource (Inter, Instrument Serif).
- backend/: Python 3.12 + FastAPI. MinerU 4.x runs locally for parsing. rank_bm25 for search. Pillow for crops.
- LLM: Gemma 4 on the organizers' server, called only through backend/app/llm.py (assume an OpenAI-compatible chat completions API; keep it easy to adapt).

## Figma (design source of truth)
- File key: dEpoBVGwqEwzOmYaKJC750. Frame node ids are listed in docs/DESIGN.md.
- Read designs through the Figma MCP server (https://mcp.figma.com/mcp): get_design_context for a frame's structure and styles, get_variable_defs for tokens, get_screenshot to compare visually, get_metadata to find node ids. In URLs, node id 3:2 is written node-id=3-2.
- Before building any screen, pull its design context and a screenshot, and match them. After building it, compare your result against the screenshot.
- Figma is a development-time tool only. The running app must never call Figma.

## Commands
- Backend: cd backend && source .venv/bin/activate && uvicorn app.main:app --reload --port 8000
- Frontend: cd frontend && npm run dev (http://localhost:5173)

## Hard rules
1. At runtime, the ONLY outbound network calls allowed are to the Gemma API. No CDNs, Google Fonts, analytics, or other external APIs. Breaking this can disqualify the team.
2. Never print or commit API keys. Keys live in backend/.env.
3. Never guess MinerU's output format. Run it on a real sample file and inspect the JSON before writing any parser.
4. Answers come only from retrieved document blocks. Every answer sentence must cite at least one source block. Anything unsupported becomes "not_found". Enforce this in code, not only in the prompt.
5. Totals and calculations are computed in Python, never by the LLM.
6. Use design tokens (CSS variables) for every color. No hard-coded hex values in components.
7. docs/ARCHITECTURE.md holds the API contract. If you change it, update the doc, the backend, and frontend/src/lib/types.ts together.
8. Work in small phases. After each phase, stop and tell us exactly how to test it.

## Conventions
- Frontend: components in src/components (one per file, PascalCase, named after the Figma components), screens in src/pages, API client in src/lib/api.ts, types in src/lib/types.ts. Mock mode (VITE_USE_MOCKS=true) serves fixtures from src/mocks using the same types.
- Backend: app/main.py (routes), app/storage.py (folders and JSON), app/parsing.py (MinerU), app/search.py (BM25 and query expansion), app/answer.py (prompting and validation), app/llm.py (Gemma client). Data lives in backend/data/.
