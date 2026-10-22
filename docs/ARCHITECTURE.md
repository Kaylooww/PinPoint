# PinPoint — Architecture

## Ingest pipeline
upload → save to data/{ws}/uploads → MinerU parse in a background task → extract blocks (text, page, locator, bbox if present) → save data/{ws}/blocks.json → rebuild the BM25 index for the workspace.

MinerU (verify every command with --help first):
- Status: mineru server status --json (start it with: mineru server start)
- Parse: mineru parse "<file>" --pages all --json (by default only the first 10 PDF pages are parsed)
- Block crop: mineru read "<block locator>" --format image --output <path>.png
- Fallback crop: render the page image with mineru read "<page locator>" --format image, then crop it with Pillow using the block's bbox. If that also fails, use the page image.
- Locator format: doc:{short_id}/tier:{tier}/page:{n}/block:{m}. Block m is the m-th blank-line-separated paragraph of page n in the parse output's markdown (a table is one block). Tier: basic (MINERU_TIER).
- Tier per file (parsing.choose_tier): PDFs with a text layer (pypdf: more than 200 extractable characters on at least 2 of the first 3 pages) and Office/HTML files use MinerU --tier flash (no OCR or layout models; e.g. Rules of Court, 196 pages: 39.5 s instead of many minutes). Scanned PDFs (no text layer), unreadable PDFs, and images keep the basic tier. Flash output has the same markdown, page/block locators (doc:{id}/tier:flash/...), bboxes in MinerU's store, and `mineru read` crops. If flash fails, the file is retried on basic. The tier and parse time are stored on the file record (tier, parse_seconds). While parsing, the progress label is "Reading N pages…" from pypdf's page count (MinerU's CLI reports no per-page progress).
- Embedding a parsed file's blocks runs on its own thread, so the parse queue (one worker) never waits on it.
- Non-PDF files are parsed without --pages (MinerU rejects it). Plain-text files (md, txt, csv) skip MinerU, which refuses them: one block per paragraph, locator text:{file_id}/page:1/block:{m}, and crop_url null (the UI shows the text).

## Ask pipeline
1. Query expansion: the LLM returns 5–10 keywords and synonyms (JSON).
2. Retrieval (hybrid): BM25 over the question plus the expansions (top 30), and cosine similarity between the question's embedding and every block's embedding (top 30), fused with reciprocal rank fusion (k=60); the top 6 are retrieved. The query is embedded with the instruction prefix "Instruct: Given a question about a client's documents, retrieve passages that answer it\nQuery: " (documents get no prefix); on the test questions it put 12/12 answers in the top 6, versus 11/12 without the prefix and 10/12 for BM25 alone.
   - Fallback (silent, mandatory): BM25 alone when LLM_PROVIDER=none (no outbound calls at all), when EMBED_BASE is unset, or when the embedding call fails or times out (EMBED_TIMEOUT_SECONDS, default 3). After a failure, embeddings are skipped for 60 s so later asks don't wait on a dead server.
   - Indexing: after a file's blocks are written (and after note changes), each block is embedded and its unit vector cached in data/{ws}/embeddings.json, keyed by a hash of model, dimensions, and text, so restarts and rescans only embed new or changed blocks. If embedding fails, the file still becomes ready; missing vectors are retried on startup (background) and on each ask (up to 32 per ask).
3. Context expansion: the 6 retrieved blocks, then the first 3 blocks of each retrieved file's page 1 (letterhead, date, addressee; round-robin across files), then each retrieved block's neighbours on the same page (±1), deduplicated, in document order within each file, at most 12 blocks. Short blocks such as a letter's date line rarely match the question's words, so this is how they reach the LLM. Block boundaries, locators, and crops are unchanged, and every context block is citable. Query expansion adds date words (date, dated, issued, month names, the year) for "when / what date / sent / signed / issued / due" questions.
4. Answer: the LLM receives the context blocks as b1…bN (N ≤ 12) and returns JSON only:
   {"status":"answered"|"not_found","answer":[{"kind":"paragraph"|"bullet"|"numbered"|"heading","text":"...","sources":["b1"]}],"quotes":{"b1":"exact supporting words from b1"},"reason":"..."}
5. Validation in code: drop items whose sources aren't in the provided ids. Answers are structured: each item has a kind, "paragraph" (a one-sentence direct answer first), "bullet" (several things), "numbered" (steps or anything in order), or "heading" (at most one or two short labels). Every non-heading item must cite at least one provided block, as before. A "heading" (up to ~6–8 words; longer ones become paragraphs) may have no sources, is not a claim, is dropped when nothing factual follows it, and never counts as the answer by itself. Stray markdown (#, **, list markers, backticks) is stripped from item text. A missing kind means "paragraph" (answers saved before this change). Extractive answers are paragraph items. If nothing is left, return not_found. On invalid JSON, retry once with a stricter prompt, then return not_found.
6. Create (or reuse cached) crops for the cited blocks only.
7. Not found → "Did you mean…?": not_found responses carry near_matches (up to 3 Citations with crops, the blocks covering the suggestion's facts first, then the LLM's named passages, then retrieval order) and optionally suggestion {text, question}, which the LLM proposes in the same JSON call. Validated in code: text is one question ending in "?" (it must not carry the answer), and every date, number, amount, and month name in text and question appears verbatim in a near-match block (case and whitespace ignored); otherwise it is dropped and only near_matches remain. The status stays not_found; the mismatched question is never answered.

## LLM modes
- generate (LLM_PROVIDER is openai_compatible — Claude Haiku via the organizers' Open WebUI server — or anthropic): the LLM does query expansion and writes the cited answer, as described above.
- extractive (LLM_PROVIDER=none, or automatic when the LLM errors or times out): skip query expansion, run BM25 on the question only, and return the top 1–3 blocks as the answer sentences, each citing its own block, with the label "Showing matching passages." Crops, the citation panel, notes, history, and folders all work the same way.
- Keep LLM calls small: at most 12 context blocks (6 retrieved plus expansion) and short JSON outputs. max_tokens is 2000 for the answer and 400 for query expansion, because the model's reasoning tokens count toward it (at 500, answers with quotes were cut off mid-JSON; at 1200, longer structured lists were). A not_found caused by invalid JSON is never cached.
- backend/app/llm.py is the only module that talks to an LLM: chat_json(system, user, max_tokens=500) -> dict, and health() -> {ok, provider, model, latency_ms, mode}; embed(texts) -> list[list[float]] (POST {EMBED_BASE}/embeddings, 32 texts per call) and embed_health(). GET /api/health reports llm, embeddings ({ok, model, dimensions, latency_ms, error?}), and mineru status.

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
AskResponse: {status: "answered"|"not_found", answer: {kind: "paragraph"|"bullet"|"numbered"|"heading", text, sources: string[]}[], citations: Citation[], reason?, searched_files, elapsed_ms, near_matches?: Citation[], suggestion?: {text, question}}
Citation: {id, number, file_id, file_name, page, locator, text, excerpt, crop_url, table?}

## Persistence
Everything lives on disk under backend/data/{ws}/ and survives restarts: workspace.json, files.json (metadata including source "upload"|"folder" and source_path), uploads/, parsed/, blocks.json, crops/, history.json, notes/ (one .md file per note), folders.json. On startup, rebuild each workspace's BM25 index from blocks.json, and reset any file stuck in "parsing" to "queued" and resume it.

## Memory
- Notes: user-written facts saved as markdown in notes/, indexed like documents, and cited with kind "note" (no crop; the UI shows the note text).
- History: every ask is stored with its question, response, thread_id, created_at, and saved flag. Answered questions are saved by default (they appear under Saved answers); not_found ones are not. PATCH saved toggles it.
- Follow-ups: /ask accepts an optional thread_id. The last 3 questions and answers in the thread go ONLY to the query-expansion step, to resolve references like "that case". Answers must still cite document or note blocks. Previous AI answers are never used as sources.

## Local folders
- The backend runs on the user's own machine, so it can read a folder the user chooses. Validate that the path exists and is a directory. Walk it read-only: max depth 5, max 200 files, max 50 MB per file, supported extensions only (pdf, png, jpg, jpeg, webp, docx, xlsx, pptx, csv, md, txt). Skip hidden folders, node_modules, .git, and system folders. Do not follow symlinks.
- Files are parsed in place, not copied. Store source_path, mtime, and size. Rescan parses new or changed files and removes deleted ones from the index. Disconnect removes the folder's files from the index. Never modify or delete anything on disk outside backend/data.
- Browser alternative: the frontend can let the user pick a folder (File System Access API, or an input with webkitdirectory) and upload its supported files through the normal upload endpoint.

## API additions
POST   /api/workspaces/{ws}/ask {"question","thread_id"?,"file_ids"?} → AskResponse plus {thread_id, history_id}. file_ids restricts retrieval (and context expansion) to those files and skips notes ("Ask about this document"); such asks are cached separately and still go to history.
GET    /api/workspaces/{ws}/history → HistoryItem[]
GET    /api/workspaces/{ws}/history/{id} → {question, response: AskResponse, thread_id, created_at, saved}
PATCH  /api/workspaces/{ws}/history/{id} {"saved": bool} → HistoryItem
GET    /api/workspaces/{ws}/notes → Note[]
POST   /api/workspaces/{ws}/notes {"text"} → Note
DELETE /api/workspaces/{ws}/notes/{id} → {"ok": true}
POST   /api/system/pick-folder → {"path": "/abs/path"} or {"path": null} if the user cancels. Opens the OS folder picker on this computer (macOS: osascript "choose folder"; Windows: PowerShell FolderBrowserDialog; no shell, 120 s timeout) and returns the chosen path without a trailing slash. It does not connect anything: POST /folders still validates the path and applies every limit. Only from localhost (request.client.host 127.0.0.1 or ::1), else 403. Other OS or failure → 501 {"error": "Folder picker not available; type the path instead."}. No network calls.
GET    /api/workspaces/{ws}/folders → Folder[]
POST   /api/workspaces/{ws}/folders {"path"} → Folder
POST   /api/workspaces/{ws}/folders/{id}/rescan → Folder
DELETE /api/workspaces/{ws}/folders/{id} → {"ok": true}
GET    /api/workspaces/{ws}/knowledge → KnowledgeStats
GET    /api/workspaces/{ws}/files/{file_id}/raw → the original file, inline, with its media type. Only files registered in files.json, looked up by id (ids match [A-Za-z0-9-]+; no paths in the URL). Uploads must resolve inside the workspace's uploads/; folder files only while their source_path is inside their connected folder; symlinks refused. 404 otherwise.
GET    /api/workspaces/{ws}/files/{file_id}/text → FileText (parsed text by page, for formats browsers can't render: docx, xlsx, pptx)
GET    /api/workspaces/{ws}/files/{file_id}/pages/{n}.png → a PDF page rendered as an image (mineru read "<page locator>" --format image, cached in crops/pages/). Registered PDFs only, looked up by id, 1 ≤ n ≤ pages; 404 otherwise. Used by the document viewer instead of a PDF library.

HistoryItem: {id, question, status, answer_preview, thread_id, created_at, saved}
Note: {id, text, created_at}
Folder: {id, path, file_count, status: "scanning"|"ready"|"failed", last_scanned_at, error?}
KnowledgeStats: {files, ready_files, pages, passages, notes, folders, last_indexed_at}
FileText: {id, name, type, page_count, pages: {page, blocks: {text, locator, table?, bbox?}[]}[]} (bbox normalized 0–1, for outlining a cited block on the page image)
FileItem gains: source: "upload"|"folder", source_path?
Citation gains: kind: "file"|"note". crop_url is null for notes and plain-text files.
Citation.text is the block's full cleaned text with its line breaks (parser artifacts stripped: page markers, HTML comments, heading and emphasis marks). Citation.excerpt is the short supporting passage: the LLM's per-source span when it is a verbatim substring of the block (whitespace and case normalized; the excerpt is cut from the block, never the LLM's copy), otherwise the 1–3 lines or sentences with the most question and answer-term overlap. Citation.table (only for table blocks) is the block's rows of cells, for rendering as a real table.

## Data layout
backend/data/{ws}/workspace.json, uploads/, parsed/, blocks.json, embeddings.json, crops/

## Environment
backend/.env: LLM_PROVIDER (openai_compatible | anthropic | none), OPENAI_COMPAT_BASE, OPENAI_COMPAT_KEY, OPENAI_COMPAT_MODEL, ANTHROPIC_API_KEY, ANTHROPIC_MODEL, LLM_TIMEOUT_SECONDS; embeddings: EMBED_BASE (the organizers' OpenAI-compatible server, venue network), EMBED_KEY, EMBED_MODEL (qwen3-embedding), EMBED_DIMENSIONS (512), optional EMBED_TIMEOUT_SECONDS (default 3)
frontend/.env.local: VITE_API_BASE, VITE_USE_MOCKS
