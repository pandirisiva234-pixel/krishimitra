# Project structure — what every file does

Rule of thumb: **routes** handle HTTP only, **services** hold the logic (testable without a server),
**models** are the database shape, **schemas** are the API shape.

## Root

| File | Responsibility |
| --- | --- |
| `README.md` | Overview, quick start, module status |
| `docker-compose.yml` | Runs PostgreSQL + backend + frontend together |
| `docker-compose.prod.yml` | Adds Caddy for automatic HTTPS on a server |
| `.env.docker.example` | Template of settings for Docker (copy to `.env`) |
| `.gitignore` | Keeps secrets, datasets, models and build output out of Git |
| `.vscode/` | Recommended extensions and Python/pytest settings |
| `deploy/Caddyfile` | HTTPS reverse proxy config |
| `deploy/backup.sh`, `deploy/backup_windows.ps1` | Database + knowledge base + uploads backups |

## backend/

| File | Responsibility |
| --- | --- |
| `app/main.py` | Creates the FastAPI app: middleware (CORS, request IDs), error handlers, rate limiter, routers; creates the service container at startup |
| `app/core/config.py` | All settings from `.env` (database, secrets, model names, limits, paths). No secrets have defaults |
| `app/core/security.py` | bcrypt password hashing, JWT create/verify |
| `app/core/exceptions.py` | App error classes and handlers that return `{"error": {code, message, request_id}}` without leaking internals |
| `app/core/logging.py` | Log format; middleware adding `X-Request-ID` and a timing line per request |
| `app/core/rate_limit.py` | SlowAPI limiter (login 5/min, AI endpoints 20/min per IP) |
| `app/db/base.py` | SQLAlchemy base class with constraint naming convention; `created_at` mixin |
| `app/db/session.py` | Engine, session factory, `get_db` dependency |
| `app/models/language.py` | `languages` table (code, NLLB code, Whisper code, TTS voice, script) |
| `app/models/user.py` | `users` (role farmer/admin, profile, location) and `admins` (admin details, 1:1) |
| `app/models/conversation.py` | `intents`, `conversation_history`, `queries`, `responses`, `feedback` |
| `app/models/disease.py` | `diseases` (curated info per class) and `disease_predictions` |
| `app/models/knowledge.py` | `documents` (knowledge files) and `weather_data` (API cache/history) |
| `app/schemas/auth.py` | Register/login/profile request and response models with phone/password validation |
| `app/schemas/assistant.py` | Transcription, question/answer, speak, feedback, conversation, search models |
| `app/schemas/other.py` | Disease, weather, documents, dashboards, admin models |
| `app/api/deps.py` | `get_current_user` (JWT check), `require_admin`, `get_services` |
| `app/api/routes/meta.py` | `GET /api/health`, `GET /api/languages` |
| `app/api/routes/auth.py` | Register, login, logout, profile get/update, change password |
| `app/api/routes/assistant.py` | `POST /voice/transcribe`, `/assistant/query`, `/assistant/speak`, audio download, `/feedback` |
| `app/api/routes/disease.py` | Predict, history, disease library, image download (owner only) |
| `app/api/routes/weather.py` | Current, forecast (+ advisories), geocode |
| `app/api/routes/knowledge.py` | Upload (background indexing), list, delete, passage search |
| `app/api/routes/conversations.py` | List, open, delete conversations |
| `app/api/routes/dashboard.py` | Farmer dashboard numbers |
| `app/api/routes/admin.py` | Admin dashboard, statistics, user management, system status |
| `app/services/container.py` | Creates each AI service once; models load lazily or at startup |
| `app/services/assistant.py` | **The pipeline**: language detection → translate → intent → weather or RAG → Gemini → translate back → TTS → save, with per-stage timings |
| `app/services/language_service.py` | Language lookups from the database |
| `app/services/speech/audio_utils.py` | FFmpeg conversion to 16 kHz mono WAV; duration via ffprobe |
| `app/services/speech/whisper_stt.py` | Faster-Whisper transcription + language identification |
| `app/services/translation/languages.py` | Default languages, Unicode script ranges, intent list |
| `app/services/translation/language_detect.py` | Text language detection by script |
| `app/services/translation/nllb_translator.py` | NLLB-200 translation (transformers or CTranslate2 int8), sentence splitting |
| `app/services/nlp/intent_classifier.py` | Loads the trained intent model; transparent keyword fallback |
| `app/services/rag/embeddings.py` | Sentence-Transformers embeddings (MiniLM) |
| `app/services/rag/vector_store.py` | ChromaDB add/query/delete |
| `app/services/rag/ingest.py` | PDF/TXT → pages → cleaning → chunks (with page numbers) → embeddings → ChromaDB |
| `app/services/rag/reranker.py` | FlashRank cross-encoder reranking |
| `app/services/rag/retriever.py` | Top-K search → rerank → relevance threshold → top-N |
| `app/services/llm/prompts.py` | Grounded system prompt, prompt builders, fallback texts |
| `app/services/llm/gemini_client.py` | Gemini calls with retries and clear error messages |
| `app/services/tts/edge_tts_service.py` | Edge-TTS with file cache and gTTS fallback |
| `app/services/disease/preprocessing.py` | OpenCV decode, blur score, resize/normalise (identical to training) |
| `app/services/disease/predictor.py` | ONNX Runtime inference, softmax, top-3 |
| `app/services/weather/openweather_client.py` | OpenWeather HTTP calls and response parsing |
| `app/services/weather/service.py` | Weather with PostgreSQL caching + advisories |
| `app/services/weather/advisories.py` | Rule-based farm advisories and daily summaries |
| `app/utils/files.py` | Upload validation (size, extension, magic bytes), safe saving, path-traversal guard |
| `app/utils/timing.py` | Stage timer used for latency analysis |
| `app/data/disease_info.json` | Description/symptoms/treatment/prevention for 38 classes (editable) |
| `alembic.ini`, `alembic/env.py`, `alembic/script.py.mako` | Migration configuration |
| `alembic/versions/*_initial_schema.py` | Migration that creates all 12 tables |
| `scripts/seed_data.py` | Inserts/updates languages, intents, diseases |
| `scripts/create_admin.py` | Creates or promotes an admin |
| `scripts/ingest_documents.py` | Bulk-indexes PDFs from `knowledge_base/documents/` |
| `tests/conftest.py` | Test database, fixtures and clearly labelled test doubles |
| `tests/test_*.py` | 63 tests: auth, assistant pipeline, voice, weather, disease, knowledge, admin, units |
| `requirements.txt`, `requirements-dev.txt` | Python dependencies |
| `.env.example` | Template of every setting |
| `Dockerfile`, `.dockerignore` | Backend container |

## frontend/

| File | Responsibility |
| --- | --- |
| `index.html`, `src/main.jsx` | Page shell and React entry point |
| `src/App.jsx` | Routes; public, guest-only, protected and admin-only areas; lazy-loaded pages |
| `src/api/client.js` | Axios instance, token header, 401 handling, readable error messages |
| `src/api/endpoints.js` | One function per backend endpoint |
| `src/context/AuthContext.jsx` | Logged-in user state, login/register/logout |
| `src/context/ToastContext.jsx` | Success/error notifications |
| `src/hooks/useRecorder.js` | Microphone recording (MediaRecorder), live level meter, 60 s limit |
| `src/components/Layout.jsx` | Sidebar navigation (collapses on mobile), user chip, logout |
| `src/components/RouteGuards.jsx` | Login-required, admin-only and guest-only routes |
| `src/components/ui.jsx` | Cards, stat tiles, spinners, empty states, confidence bar, authenticated audio/image |
| `src/components/LanguageSelect.jsx` | Language dropdown loaded from the API |
| `src/components/CameraCapture.jsx` | Live camera preview and capture (back camera on phones) |
| `src/components/SourceList.jsx` | Expandable list of answer sources |
| `src/pages/Landing.jsx` | Public home page |
| `src/pages/Register.jsx`, `Login.jsx` | Account creation and login with validation |
| `src/pages/Dashboard.jsx` | Farmer dashboard: counts, weather + advisories, recent questions and scans |
| `src/pages/VoiceAssistant.jsx` | Record → transcribe → edit → ask; answers with audio, sources, English toggle, feedback |
| `src/pages/DiseaseDetection.jsx` | Upload or camera, prediction result, treatment, listen in your language, history |
| `src/pages/Weather.jsx` | Location search, current weather, advisories, 5-day chart |
| `src/pages/Knowledge.jsx` | Passage search over the knowledge base, document list |
| `src/pages/History.jsx` | Conversation list and detail, continue or delete |
| `src/pages/Profile.jsx` | Profile, language, GPS location, password change |
| `src/pages/admin/AdminDashboard.jsx` | Totals, charts (per day, languages, intents, diseases), system status |
| `src/pages/admin/AdminUsers.jsx` | Search, paginate, activate/disable, change role |
| `src/pages/admin/AdminDocuments.jsx` | Upload and delete knowledge documents, live indexing status |
| `src/styles/theme.css` | Green theme, layout, responsive rules |
| `src/utils/format.js`, `validation.js` | Display helpers and form validation (mirrors backend rules) |
| `src/test/*` | 17 Vitest tests (validation, components, login/register flows) |
| `vite.config.js` | Dev server with `/api` proxy to port 8000; test setup |
| `nginx.conf`, `Dockerfile` | Production serving and `/api` proxy |

## ml/

| File | Responsibility |
| --- | --- |
| `disease_detection/src/prepare_split.py` | Removes corrupt/duplicate images, class distribution, fixed stratified 70/15/15 split |
| `disease_detection/src/eda.py` | Image size/colour/blur statistics and sample grid |
| `disease_detection/src/preprocess.py` | Same preprocessing as the backend |
| `disease_detection/src/dataset.py` | PyTorch datasets, augmentation, class weights |
| `disease_detection/src/models.py` | Baseline CNN, MobileNetV2, MobileNetV3-Large, EfficientNet-B0 |
| `disease_detection/src/train.py` | Two-stage transfer learning, early stopping, curves |
| `disease_detection/src/tune.py` | Small grid search on the validation set |
| `disease_detection/src/evaluate.py` | Accuracy, precision, recall, F1, top-3, confusion matrix, CPU latency |
| `disease_detection/src/compare.py` | Model comparison table and chart from saved metrics |
| `disease_detection/src/prepare_external.py` | PlantDoc field test set for independent evaluation |
| `disease_detection/src/export_onnx.py` | ONNX export + check that ONNX and PyTorch agree |
| `disease_detection/configs/*.yaml` | Hyperparameters per model; PlantDoc→PlantVillage class map |
| `disease_detection/notebooks/disease_detection_colab.ipynb` | Runs the whole experiment on Colab GPU |
| `intent_classification/train_intent.py` | TF-IDF vs embedding classifier vs keyword baseline; saves a model only if it beats the baseline |
| `intent_classification/data/intents_seed.csv` | 240 development questions (author-written, see note in the script) |
| `evaluation/stt_eval.py` | WER/CER/language-ID accuracy per language and model size |
| `evaluation/translation_eval.py` | chrF++/BLEU for NLLB both directions |
| `evaluation/rag_eval.py` | hit@k and MRR: pivot vs pivot+rerank vs multilingual |
| `evaluation/pipeline_timings.py` | Latency per stage from real stored requests |
| `evaluation/data/*` | Templates and instructions for the test sets you create |
