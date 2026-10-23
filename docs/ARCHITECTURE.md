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
- Encrypted PDFs (parsing.prepare_pdf, pypdf[crypto]): if the PDF opens with an empty password (owner restrictions only, e.g. copying disabled), a decrypted working copy is written to parsed/{file_id}.decrypted.pdf and parsed instead; page numbers are unchanged and the user's file (upload or folder original) is never modified. If it needs a real password, the file fails with "This PDF is password-protected. Unlock it, then upload it again."
- Long PDFs (more than 40 pages) are parsed 20 pages at a time (`mineru parse --pages a-b`; page markers stay absolute). After each chunk its blocks are written and the index rebuilt, so early pages are searchable while the rest parse. Progress label: "Reading pages 41–60 of 111". A failing chunk is retried once (on the default tier if the fast one failed), then skipped; the file still becomes ready with error = "Pages 61–80 couldn't be read." (shown as a warning note on a ready file). The saved parse is {"chunks": [...]}.
- Failures: MinerU errors and timeouts set status "failed" with a short human message (shown in red). A watchdog checks every minute: a file in "parsing" with no progress for 10 minutes is requeued once, then failed with "Parsing stopped responding. Try uploading the file again."
- HTML tables (MinerU writes <table> markup on the basic tier) become one line per row, cells joined with " · ", and set the block's table field. For the LLM, a block longer than the per-block limit keeps its first line plus the lines that best match the question, so a "TOTAL ASSETS" row near the end of a balance sheet isn't cut off.
- Embedding a parsed file's blocks runs on its own thread, so the parse queue (one worker) never waits on it.
- Heading breadcrumbs (parsing.add_breadcrumbs): walking each file's blocks in reading order, headings are detected from BOOK, PART, TITLE, ARTICLE, CHAPTER, RULE, SECTION/Sec./§, CLAUSE, SCHEDULE, ANNEX (Roman or Arabic numerals, case-insensitive) and numbered headings ("1." / "1.1"); an ARTICLE line takes its title from a following all-caps line ("Article VI — The Legislative Department"). Levels nest: a new Article resets everything below it; a new Section replaces the previous one. Table-of-contents pages (mostly bare heading lines) open no headings. Each block gets path (labels, outermost first) and heading_ids (those headings' block ids). scripts/rebuild_blocks.py re-extracts blocks from saved parses (no MinerU calls; file ids kept; blocks.json backed up to blocks.json.bak).
- Non-PDF files are parsed without --pages (MinerU rejects it). Plain-text files (md, txt, csv) skip MinerU, which refuses them: one block per paragraph, locator text:{file_id}/page:1/block:{m}, and crop_url null (the UI shows the text).

## Ask pipeline
1. Query expansion: the LLM returns 5–10 keywords and synonyms (JSON).
2. Retrieval (hybrid): BM25 over the question plus the expansions (top 30), and cosine similarity between the question's embedding and every block's embedding (top 30), fused with reciprocal rank fusion (k=60); the top 6 are retrieved. Query and document prefixes follow the embedding model: embeddinggemma (the default, local via Ollama) gets "task: search result | query: " on questions and "title: none | text: " on passages; nomic-embed-text gets "search_query: " / "search_document: "; any other model (e.g. qwen3-embedding) gets the instruction "Instruct: Given a question about a client's documents, retrieve passages that answer it\nQuery: " on questions only. With qwen3-embedding the prefix put 12/12 test answers in the top 6, versus 11/12 without it and 10/12 for BM25 alone.
   - Fallback (silent, mandatory): BM25 alone when LLM_PROVIDER=none (no outbound calls at all), when EMBED_BASE is unset, when the embedding call fails or times out (EMBED_TIMEOUT_SECONDS, default 3; 15 locally so a cold model load fits), or while the workspace's vectors are from another embedding model (see Model switch below). After a failure, embeddings are skipped for 60 s so later asks don't wait on a dead server.
   - Indexing: after a file's blocks are written (and after note changes), each block is embedded and its unit vector cached in data/{ws}/embeddings.json, keyed by a hash of model, dimensions, and text, so restarts and rescans only embed new or changed blocks. If embedding fails, the file still becomes ready; missing vectors are retried on startup (background) and on each ask (up to 32 per ask).
   - Model switch: embeddings.json is {model, dimensions, complete, vectors}. When model or dimensions differ from EMBED_MODEL / EMBED_DIMENSIONS (or the file is the older flat {hash: vector} map), every block is re-embedded on a background thread from blocks.json, never re-parsed, saved every 256 blocks with complete=false so a restart resumes; the old model's vectors are dropped. Until complete, search uses BM25 alone. create_note never runs a whole-workspace re-embed inside the request.
   - BM25 indexes each block as "<path joined by ' > '>: <text>", so "Article VI" or "Rule 41" questions find the right passages. Embeddings keep the passage text alone, so breadcrumb changes need no mass re-embed (a remote embedding server may rate-limit large batches).
3. Context expansion: the 6 retrieved blocks, then the first 3 blocks of each retrieved file's page 1 (letterhead, date, addressee; round-robin across files), then each retrieved block's neighbours on the same page (±1), deduplicated, in document order within each file, at most 12 blocks (8 for a local model, see LLM modes). Short blocks such as a letter's date line rarely match the question's words, so this is how they reach the LLM. Block boundaries, locators, and crops are unchanged, and every context block is citable. Query expansion adds date words (date, dated, issued, month names, the year) for "when / what date / sent / signed / issued / due" questions.
   Then up to 4 heading blocks of the retrieved passages (e.g. the "ARTICLE VI" block) are added as citable context, so a claim about the location can cite the heading and its crop.
4. Answer: the LLM receives the context blocks as b1…bN (N ≤ 16; ≤ 8 for a local model), each shown with its path, e.g. "[b3] (file, page 11) Article VI — The Legislative Department > Section 21:", and returns JSON only. The prompt asks it to name the full location (e.g. "Article VI, Section 21") and never to say the article isn't named when a path is given:
   {"status":"answered"|"not_found","answer":[{"kind":"paragraph"|"bullet"|"numbered"|"heading","text":"...","sources":["b1"]}],"quotes":{"b1":"exact supporting words from b1"},"reason":"..."}
5. Validation in code: drop items whose sources aren't in the provided ids. Answers are structured: each item has a kind, "paragraph" (a one-sentence direct answer first), "bullet" (several things), "numbered" (steps or anything in order), or "heading" (at most one or two short labels). Every non-heading item must cite at least one provided block, as before. A "heading" (up to ~6–8 words; longer ones become paragraphs) may have no sources, is not a claim, is dropped when nothing factual follows it, and never counts as the answer by itself. Stray markdown (#, **, list markers, backticks) is stripped from item text. A missing kind means "paragraph" (answers saved before this change). Extractive answers are paragraph items. If nothing is left, return not_found. On invalid JSON, retry once with a stricter prompt, then return not_found.
6. Create (or reuse cached) crops for the cited blocks only.
7. Not found → "Did you mean…?": not_found responses carry near_matches (up to 3 Citations with crops, the blocks covering the suggestion's facts first, then the LLM's named passages, then retrieval order) and optionally suggestion {text, question}, which the LLM proposes in the same JSON call. Validated in code: text is one question ending in "?" (it must not carry the answer), and every date, number, amount, and month name in text and question appears verbatim in a near-match block (case and whitespace ignored); otherwise it is dropped and only near_matches remain. The status stays not_found; the mismatched question is never answered.

## LLM modes
- generate (LLM_PROVIDER is openai_compatible — by default gemma4:e2b on local Ollama, http://localhost:11434/v1 — or anthropic): the LLM does query expansion and writes the cited answer, as described above.
- Local server (OPENAI_COMPAT_BASE on localhost / 127.0.0.1 / ::1): requests add temperature 0, reasoning_effort "none" (LLM_REASONING_EFFORT overrides it; thinking made answers 4–10× slower), and response_format {"type": "json_object"}. If the model refuses JSON mode (Ollama 0.40 with gemma4 returns HTTP 501 "structured output is unavailable"), the call is repeated without it and the refusal is remembered. A remote server gets none of these three (the organizers' Open WebUI rejected them). Context is capped at 8 blocks: the 6 retrieved plus up to 2 headings or neighbours; retrieved blocks are never dropped.
- extractive (LLM_PROVIDER=none, or automatic when the LLM errors or times out): skip query expansion, run BM25 on the question only, and return the top 1–3 blocks as the answer sentences, each citing its own block, with the label "Showing matching passages." Crops, the citation panel, notes, history, and folders all work the same way.
- Keep LLM calls small: at most 12 context blocks (8 locally; 6 retrieved plus expansion) and short JSON outputs. max_tokens is 2000 for the answer and 400 for query expansion, because the model's reasoning tokens count toward it (at 500, answers with quotes were cut off mid-JSON; at 1200, longer structured lists were). A not_found caused by invalid JSON is never cached. Before parsing, chat_json strips thinking (<think>…</think> and similar) and code fences, takes the first JSON object when prose follows it, moves a brace a small model closed early ({…},"suggestion": {…}) to the end, and escapes quotes copied unescaped from documents (“Invoice", …); a reply cut off mid-string still fails and gets the one stricter retry.
- backend/app/llm.py is the only module that talks to an LLM: chat_json(system, user, max_tokens=500) -> dict, and health() -> {ok, provider, model, latency_ms, mode}; embed(texts) -> list[list[float]] (POST {EMBED_BASE}/embeddings with dimensions, 32 texts per call) and embed_health(). GET /api/health reports llm, embeddings ({ok, model, dimensions, latency_ms, error?}), and mineru status.

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
Citation: {id, number, file_id, file_name, page, locator, text, excerpt, crop_url, table?, path?}

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
DELETE /api/workspaces/{ws} → {"ok": true}. Deletes backend/data/{ws} (uploads, parses, blocks, vectors, crops, notes, history) after cancelling its queued and parsing files; drops its search index and cached answers. Connected folders' originals are never touched. Background writes into a deleted workspace are dropped so its folder doesn't come back. The demo workspace is seeded only when no workspaces exist, so a deleted one stays deleted. 404 if unknown.
DELETE /api/workspaces/{ws}/files/{id} → {"ok": true}. Deletes an uploaded file: its record, blocks, upload copy, saved parse, decrypted copy, crops, and rendered pages no other file uses. A queued file is skipped by the parse queue; a file being read has its mineru call killed and the job discards its output (this is "Cancel upload", the X on a queued or parsing row). Folder files → 409 (remove them from the folder and rescan). Unknown id → 404.
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
backend/.env: LLM_PROVIDER (openai_compatible | anthropic | none), OPENAI_COMPAT_BASE (http://localhost:11434/v1), OPENAI_COMPAT_KEY (ollama), OPENAI_COMPAT_MODEL (gemma4:e2b), ANTHROPIC_API_KEY, ANTHROPIC_MODEL, LLM_TIMEOUT_SECONDS (120 locally), optional LLM_REASONING_EFFORT (local only, default none); embeddings: EMBED_BASE (http://localhost:11434/v1), EMBED_KEY (ollama), EMBED_MODEL (embeddinggemma), EMBED_DIMENSIONS (768), optional EMBED_TIMEOUT_SECONDS (default 3; 15 locally)
frontend/.env.local: VITE_API_BASE, VITE_USE_MOCKS
