# PinPoint — Architecture

## Ingest pipeline
upload → save to data/{ws}/uploads → MinerU parse in a background task → extract blocks (text, page, locator, bbox if present) → save data/{ws}/blocks.json → rebuild the BM25 index for the workspace.

MinerU (verify every command with --help first):
- Status: mineru server status --json (start it with: mineru server start)
- Parse: mineru parse "<file>" --pages all --json (by default only the first 10 PDF pages are parsed)
- Block crop: mineru read "<block locator>" --format image --output <path>.png
- Fallback crop: render the page image with mineru read "<page locator>" --format image, then crop it with Pillow using the block's bbox. If that also fails, use the page image.
- Locator format: doc:{short_id}/tier:{tier}/page:{n}/block:{m}

## Ask pipeline
1. Query expansion: Gemma returns 5–10 keywords and synonyms (JSON).
2. Retrieval: top 8 blocks by BM25 over the question plus the expansions.
3. Answer: Gemma receives the blocks as b1…b8 and returns JSON only:
   {"status":"answered"|"not_found","answer":[{"text":"...","sources":["b1"]}],"reason":"..."}
4. Validation in code: drop sentences whose sources aren't in the provided ids. If nothing is left, return not_found. On invalid JSON, retry once with a stricter prompt, then return not_found.
5. Create (or reuse cached) crops for the cited blocks only.

## API contract (frontend/src/lib/types.ts must match)
GET  /api/health → {"ok": true}
GET  /api/workspaces → Workspace[]
POST /api/workspaces {"name","industry"} → Workspace
GET  /api/workspaces/{ws}/files → FileItem[]
POST /api/workspaces/{ws}/files (multipart, field "files") → FileItem[]
POST /api/workspaces/{ws}/ask {"question"} → AskResponse
GET  /api/crops/{crop_id}.png → image

Workspace: {id, name, industry, file_count, updated_at}
FileItem: {id, name, type: "pdf"|"image"|"doc"|"sheet"|"slides"|"other", pages, size_bytes, status: "queued"|"parsing"|"ready"|"failed", progress_label?, error?}
AskResponse: {status: "answered"|"not_found", answer: {text, sources: string[]}[], citations: Citation[], reason?, searched_files, elapsed_ms}
Citation: {id, number, file_id, file_name, page, locator, text, crop_url}

## Persistence
Everything lives on disk under backend/data/{ws}/ and survives restarts: workspace.json, files.json (metadata including source "upload"|"folder" and source_path), uploads/, parsed/, blocks.json, crops/, history.json, notes/ (one .md file per note), folders.json. On startup, rebuild each workspace's BM25 index from blocks.json, and reset any file stuck in "parsing" to "queued" and resume it.

## Memory
- Notes: user-written facts saved as markdown in notes/, indexed like documents, and cited with kind "note" (no crop; the UI shows the note text).
- History: every ask is stored with its question, response, thread_id, created_at, and saved flag.
- Follow-ups: /ask accepts an optional thread_id. The last 3 questions and answers in the thread go ONLY to the query-expansion step, to resolve references like "that case". Answers must still cite document or note blocks. Previous AI answers are never used as sources.

## Local folders
- The backend runs on the user's own machine, so it can read a folder the user chooses. Validate that the path exists and is a directory. Walk it read-only: max depth 5, max 200 files, max 50 MB per file, supported extensions only (pdf, png, jpg, jpeg, webp, docx, xlsx, pptx, csv, md, txt). Skip hidden folders, node_modules, .git, and system folders. Do not follow symlinks.
- Files are parsed in place, not copied. Store source_path, mtime, and size. Rescan parses new or changed files and removes deleted ones from the index. Disconnect removes the folder's files from the index. Never modify or delete anything on disk outside backend/data.
- Browser alternative: the frontend can let the user pick a folder (File System Access API, or an input with webkitdirectory) and upload its supported files through the normal upload endpoint.

## API additions
POST   /api/workspaces/{ws}/ask {"question","thread_id"?} → AskResponse plus {thread_id, history_id}
GET    /api/workspaces/{ws}/history → HistoryItem[]
GET    /api/workspaces/{ws}/history/{id} → {question, response: AskResponse, thread_id, created_at, saved}
PATCH  /api/workspaces/{ws}/history/{id} {"saved": bool} → HistoryItem
GET    /api/workspaces/{ws}/notes → Note[]
POST   /api/workspaces/{ws}/notes {"text"} → Note
DELETE /api/workspaces/{ws}/notes/{id} → {"ok": true}
GET    /api/workspaces/{ws}/folders → Folder[]
POST   /api/workspaces/{ws}/folders {"path"} → Folder
POST   /api/workspaces/{ws}/folders/{id}/rescan → Folder
DELETE /api/workspaces/{ws}/folders/{id} → {"ok": true}
GET    /api/workspaces/{ws}/knowledge → KnowledgeStats

HistoryItem: {id, question, status, answer_preview, thread_id, created_at, saved}
Note: {id, text, created_at}
Folder: {id, path, file_count, status: "scanning"|"ready"|"failed", last_scanned_at, error?}
KnowledgeStats: {files, ready_files, pages, passages, notes, folders, last_indexed_at}
FileItem gains: source: "upload"|"folder", source_path?
Citation gains: kind: "file"|"note". crop_url is null for notes.

## Data layout
backend/data/{ws}/workspace.json, uploads/, parsed/, blocks.json, crops/

## Environment
backend/.env: GEMMA_API_BASE, GEMMA_API_KEY, GEMMA_MODEL
frontend/.env.local: VITE_API_BASE, VITE_USE_MOCKS
