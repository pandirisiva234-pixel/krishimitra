# Testing

## Automated tests

| Suite | Command | Count | Result on 13 Nov 2026 (Linux, Python 3.13, PostgreSQL 16) |
| --- | --- | --- | --- |
| Backend (pytest) | `cd backend; pytest -v` | 63 | 63 passed |
| Frontend (Vitest) | `cd frontend; npm test` | 17 | 17 passed |
| Frontend build | `cd frontend; npm run build` | – | built successfully |
| Migration up/down | `alembic downgrade base; alembic upgrade head` | – | both directions succeeded |
| Browser check (Chrome, desktop 1366 px + phone 390 px) | manual script with Playwright | 13 pages | all rendered, no console errors after two fixes (see below) |

Run them yourself on Windows; your results are the ones to report.

### What the backend tests use

| Component | In tests | Why |
| --- | --- | --- |
| PostgreSQL | **real** (`krishimitra_test` database) | Database behaviour (constraints, cascades, statistics SQL) must be tested for real |
| ChromaDB, chunking, PDF parsing | **real** | Indexing and retrieval logic |
| FFmpeg audio conversion | **real** (generated audio files) | Recording formats from browsers |
| ONNX Runtime disease inference | **real**, with a tiny 3-class ONNX model built in the test | Checks preprocessing → inference → softmax → database |
| OpenWeather | real client code, HTTP mocked with `respx` | No key needed; checks parsing, caching, advisories |
| Whisper, NLLB, MiniLM, Gemini, Edge-TTS | **test doubles** (`FakeSTT`, `FakeTranslator`, `HashEmbedder`, `FakeLLM`, `FakeTTS` in `conftest.py`) | Need GB-sized downloads or paid keys; they are evaluated with real models by `ml/evaluation/` scripts instead |

The test doubles return deterministic, obviously artificial outputs (e.g. `<tel_Telu> ...`), so a test can never
be mistaken for real model output.

### Coverage by area

- **Authentication:** registration, phone normalisation, duplicate phone, weak passwords, unsupported language,
  login by phone/email, identical error for wrong user vs wrong password, missing/invalid/expired token, profile
  update, password change, disabled accounts.
- **Assistant:** Telugu question end-to-end, English question answered in Telugu, follow-ups in one
  conversation, honest fallback when nothing relevant is found (Gemini not called), model's NOT_IN_KNOWLEDGE_BASE
  respected, greeting without AI call, weather intent with and without location, speech output and download,
  path-traversal attempt, feedback once only, users cannot see each other's data, delete conversation.
- **Voice:** real WebM/Opus conversion and duration, low-confidence language falls back to the profile language
  (second forced pass), fake audio, too-short audio and wrong extensions rejected.
- **Disease:** real ONNX inference, uncertain prediction below threshold, blur detection, history privacy,
  non-image and oversized files rejected, disease library has treatment and prevention for all 38 classes.
- **Knowledge base:** upload → background indexing → search → delete removes vectors; PDF page numbers kept;
  farmers cannot upload or delete.
- **Admin:** farmers get 403 on all admin routes; dashboard and statistics match the data created in the test;
  search, role change, self-lockout prevented; system status.
- **Units:** script-based language detection for all 5 languages (and the romanised-text limitation), sentence
  splitting, text cleaning, chunking, keyword intents, password hashing, file magic bytes.

### Bugs found by testing and fixed

1. Assistant page crashed in current Chrome: `scrollIntoView()` now returns a Promise, which React treated as an
   effect cleanup. Fixed by not returning it from the effect.
2. Admins landed on the farmer dashboard after login: the guest-route redirect raced the login redirect. Fixed
   in `RouteGuards.jsx`.
3. An English question with Telugu selected would have been "translated" as if it were Telugu. Fixed: the
   question language is detected from the text; the dropdown sets the answer language.
4. "New users in 30 days" counted admins. Fixed to count farmers only.
5. Keyword intents missed "white flies". Added common pest spellings.

## Manual end-to-end checks on your PC (with internet and API keys)

Do these after Step 8 of SETUP_WINDOWS.md and note the result of each in your test report.

| # | Action | Expected |
| --- | --- | --- |
| 1 | Admin uploads a crop PDF | Status goes processing → indexed; chunks > 0 |
| 2 | Knowledge page: search a phrase from the PDF | That passage is in the top results with the right page |
| 3 | Voice assistant: speak a Telugu question about the PDF | Transcript in Telugu script; language "TE" |
| 4 | Ask it | Telugu answer with [1]-style citations, sources expandable, audio plays |
| 5 | Ask something not in the PDFs | "could not find… KVK" message, marked not from the knowledge base |
| 6 | Repeat 3–4 in Hindi, Tamil, Kannada, English | Same behaviour |
| 7 | Set location in Profile, ask "will it rain tomorrow?" | Weather-based answer, source "OpenWeather" |
| 8 | Weather page | Current conditions, 5-day chart, advisories |
| 9 | Disease page: upload a PlantVillage test image | Correct class, high confidence, treatment shown, "Listen" works |
| 10 | Upload a random non-leaf photo | Low confidence → "uncertain" |
| 11 | Admin overview | Counts and charts reflect steps 1–10 |
| 12 | Phone browser over HTTPS (after deployment) | Mic and camera work; layout fits the screen |
