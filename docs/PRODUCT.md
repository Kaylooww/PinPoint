# PinPoint — Product

## Pitch
Businesses like law offices, accounting firms, real estate agencies, and insurance companies handle huge volumes of documents every day, and the information they need is scattered across photos, scans, PDFs, and spreadsheets. Finding one fact means opening file after file. PinPoint lets you ask a plain-language question across all those files at once. In seconds, you get the answer along with a snapshot of exactly where it came from.

## Users
Staff at document-heavy firms (legal, real estate, accounting, insurance) who handle confidential client files. The product is SaaS, with one workspace per client.

## MVP features (must work live)
1. Workspaces: list them, create one (name plus industry). Seed a demo workspace, "Reyes & Partners".
2. Files: upload multiple files (PDF, images, DOCX, XLSX, PPTX). Show parsing status per file (queued, parsing, ready, failed).
3. Ask: ask a question about a workspace and get an answer whose sentences carry numbered citations.
4. Proof: each citation shows a cropped image of the source block, plus file name and page. Clicking it opens a side panel with a larger view and the extracted text.
5. Honesty: if the files don't contain the answer, show "Not found in these files" with a reason.
6. Empty, loading, and error states.
7. Light and dark mode, defaulting to the system setting and remembered on the device.
8. Recent questions per workspace (stored in the browser).
9. Persistent knowledge base and memory: everything a workspace learns (files, parsed passages, notes, question history) is saved on disk and survives restarts. Users can save facts as Notes ("Remember: the client prefers email updates"); notes are searched and cited like documents. Every question is kept in History, answers can be Saved, and follow-up questions keep the conversation context.
10. Local files: users can add a whole folder from their computer, either by picking it in the browser (uploads its files) or by connecting a local folder path that PinPoint reads in place and can rescan for new or changed files. PinPoint never modifies or deletes the user's files.

## Static only (no logic today)
Landing page with pricing (no payments), sign-in screen (Continue just enters the app), settings members list, Share button.

## Out of scope
Payments, real authentication, invites, sharing, email integration, mobile layouts.

## Demo script
Load "Reyes & Partners", which holds a scanned PDF, a phone photo of a document, and a spreadsheet. Ask a question worded differently from the document. Ask one that needs a photo. Ask one with no answer. Click a citation to show the proof.
