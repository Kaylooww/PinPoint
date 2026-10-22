# PinPoint — Demo Runbook

For whoever drives the live demo. Everything runs on this laptop; the only outbound call is to the organizers' LLM server.

## 1. Start (in this order, three terminals)

```sh
# 1. MinerU parse server (basic tier). Run it from the repo root so its files stay git-ignored.
mineru server start
mineru server status --json          # parse_server.local.healthy must be true (can take ~30 s)

# 2. Backend
cd backend && source .venv/bin/activate && uvicorn app.main:app --reload --port 8000

# 3. Frontend
cd frontend && npm run dev           # http://localhost:5173
```

Fresh demo workspace (wipes and rebuilds Reyes & Partners, waits until every file is ready):

```sh
cd backend && .venv/bin/python scripts/reset_demo.py
```

It uses `backend/demo_files/`, or `backend/samples/` if that folder is missing or empty. File names show in the UI as-is, so give demo files readable names (e.g. `Lease_Agreement_Scan.pdf`, `Receipt_Photo.jpg`).

## 2. Pre-demo checklist (15 minutes before)

- [ ] Laptop on power, notifications off, browser zoom 100%, window at least 1440 px wide.
- [ ] Venue Wi-Fi works: `curl -s http://localhost:8000/api/health` shows `"llm": {"ok": true, "mode": "generate"}`. If it says `extractive`, see the fallback plan.
- [ ] MinerU healthy: `mineru server status --json` → `parse_server.local.healthy: true`.
- [ ] `/api/health` shows `"mineru": {"ok": true}`.
- [ ] `reset_demo.py` ran and printed `Done: N/N files ready`.
- [ ] Answer cache warmed, as the **last** step after the final backend start (a backend restart clears the cache): `cd backend && .venv/bin/python scripts/warm_cache.py`. It asks every question in `docs/DEMO_QUESTIONS.md` and prints each status. Warm answers come back instantly, and their crops are already on disk.
- [ ] The file to upload live is on the Desktop (a photo or PDF not already in the workspace).
- [ ] Theme set to Light; dark mode is shown during the demo.
- [ ] No git checkout or pull in this folder while the servers run (it can stall Vite's Tailwind step; see fallback plan).
- [ ] Backup video open in another window.

## 3. Click-by-click script (about 3 minutes)

The questions below are verified against the current sample files. Swap in the final ones from `docs/DEMO_QUESTIONS.md`.

1. **Landing → Sign in → Workspaces.** Open http://localhost:5173. Click **Get started**, then **Continue**. Say: "One workspace per client." (Until the Landing patch lands, `/` opens Reyes & Partners' Ask tab directly; start from the sidebar's **Workspaces** instead.)
2. **Open Reyes & Partners → Files.** Point out the scanned contract and the phone photo of a receipt, both **Ready**, and the stats line ("2 files · 3 pages · 59 passages indexed").
3. **Upload live.** Drag the Desktop file onto the drop zone. It goes **Queued → Parsing → Ready** while you talk: "It reads scans and photos locally; nothing leaves this laptop except the question."
4. **Ask (worded differently from the document).** Go to **Ask** and type:
   *"How much is the penalty if the rented car is taken outside Cebu?"*
   → Answer with numbered citations [1] [2], from the scanned contract.
5. **Show the proof.** Click citation **[1]**. The panel shows the highlighted crop of the exact paragraph, the file and page, and the extracted text. Press **Esc**.
6. **Follow-up.** Click **Ask a follow-up** and type *"Who is the renter named in that agreement?"* → it answers in the same thread. (Avoid bare one-word follow-ups like "Who is the renter?": "renter" is in almost every clause, so retrieval can miss the paragraph and the answer is Not found.)
7. **Save.** Click **Save** on the first answer. Open **Memory → Saved answers** to show it is kept, plus the full **History**.
8. **A question that needs the photo.** Back on **Ask**, click **New question**:
   *"What is the invoice number on the receipt?"* → `00544947`, cited from the phone photo.
9. **Honesty.** *"When is the filing deadline for the Santos case?"* → **Not found in these files**, with the reason. Say: "It never guesses. If it can't cite it, it says so."
10. **Memory (optional, if time).** Memory → Notes: add *"The client prefers updates by email, not phone calls."* Then ask *"How does the client want to be updated?"* → answered and cited from the **Note**.
11. **Dark mode.** Click the moon in the sidebar's theme toggle. Everything stays readable; the highlight on the crops is still visible.

## 4. Fallback plan

| Problem | What to do |
|---|---|
| Venue Wi-Fi down, or the LLM server errors or is slow | Nothing to do live: answers automatically switch to **extractive mode** ("Showing matching passages") with the same citations and crops. To force it for the rest of the demo, set `LLM_PROVIDER=none` in `backend/.env` and restart the backend; this makes no outbound calls at all. |
| A live upload fails or takes too long | Skip it. The pre-loaded files already cover every question. |
| MinerU stops | Already-parsed files and warmed answers keep working (the index and crops are on disk). Only new uploads need MinerU: run `mineru server restart`. |
| The page suddenly has no styling (giant icons, plain text) | Vite's Tailwind step stalled after files changed under it (for example a git checkout while it was running). Stop `npm run dev` and start it again, then reload the browser. |
| Backend crashes | Restart it with the command above. All workspaces, files, notes, and history reload from `backend/data/`. |
| The demo workspace looks wrong | `cd backend && .venv/bin/python scripts/reset_demo.py` (about 10 s with cached parses), then re-warm the cache. |
| Anything else | Switch to the backup video. |

## 5. After the demo

Leave everything running for judges' questions. Good extra moves: connect a local folder (Files → Add files → Connect a local folder), and show that Rescan picks up a new file.
