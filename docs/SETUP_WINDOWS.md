# Setup on Windows 11 with VS Code (step by step)

Do the steps in order. After each step there is a **check**. Do not continue until the check works.
Commands are for **PowerShell** (VS Code: *Terminal → New Terminal*). "Project folder" means the
`krishimitra` folder you unzipped.

---

## Step 1 — Install the tools

Open PowerShell **as Administrator** and run these one by one (`winget` is built into Windows 11):

```powershell
winget install -e --id Python.Python.3.12
winget install -e --id OpenJS.NodeJS.LTS
winget install -e --id PostgreSQL.PostgreSQL.16
winget install -e --id Gyan.FFmpeg
winget install -e --id Git.Git
winget install -e --id Microsoft.VisualStudioCode
```

During PostgreSQL setup, write down the password you choose for the `postgres` user.

**Close and reopen** PowerShell (so the new programs are on PATH), then **check**:

```powershell
py -3.12 --version     # Python 3.12.x
node --version         # v22 or newer
npm --version
ffmpeg -version        # first line starts with "ffmpeg version"
psql --version         # psql (PostgreSQL) 16.x
```

> `psql` not found? Add `C:\Program Files\PostgreSQL\16\bin` to PATH:
> Start → "Edit the system environment variables" → Environment Variables → Path → New. Reopen PowerShell.

**VS Code extensions** (Ctrl+Shift+X): *Python*, *Pylance*, *ESLint*, *Prettier*, *Thunder Client* (to test APIs).
Opening the project folder in VS Code will also suggest them (`.vscode/extensions.json`).

---

## Step 2 — Create the database

```powershell
psql -U postgres
```
Enter the postgres password, then type (change the password):

```sql
CREATE ROLE krishimitra LOGIN PASSWORD 'MyStrongPass123' CREATEDB;
CREATE DATABASE krishimitra OWNER krishimitra;
CREATE DATABASE krishimitra_test OWNER krishimitra;
\q
```

**Check:** `psql -U krishimitra -d krishimitra -c "SELECT 1;"` prints `1`.

---

## Step 3 — Backend environment

```powershell
cd path\to\krishimitra\backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

> Error *"running scripts is disabled on this system"*? Run once:
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` and try again.

Your prompt now starts with `(.venv)`. Install packages (PyTorch CPU first; about 1–2 GB of downloads):

```powershell
python -m pip install --upgrade pip
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements-dev.txt
```

**Check:** `python -c "import fastapi, torch, faster_whisper, chromadb; print('ok')"` prints `ok`.

In VS Code: Ctrl+Shift+P → *Python: Select Interpreter* → choose `backend\.venv\Scripts\python.exe`.

---

## Step 4 — Configure `.env`

```powershell
copy .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Open `backend\.env` in VS Code and set:

| Setting | Value |
| --- | --- |
| `DATABASE_URL` | `postgresql+psycopg://krishimitra:MyStrongPass123@localhost:5432/krishimitra` |
| `JWT_SECRET_KEY` | the random string printed above |
| `GEMINI_API_KEY` | from <https://aistudio.google.com/apikey> |
| `OPENWEATHER_API_KEY` | from <https://home.openweathermap.org/api_keys> (free; activation can take up to 2 hours) |

The app starts without the two API keys; those features just show "not configured" until you add them.

---

## Step 5 — Create tables and seed data

```powershell
alembic upgrade head
python -m scripts.seed_data
python -m scripts.create_admin --name "Pandri" --phone 9876543210 --email you@example.com
```

**Check:** the seed prints `languages: 5 created`, `intents: 8 created`, `diseases: 38 created`.
`psql -U krishimitra -d krishimitra -c "\dt"` lists 12 tables plus `alembic_version`.

---

## Step 6 — Run and test the backend

```powershell
pytest                                   # expect: 63 passed
uvicorn app.main:app --reload
```

Open <http://127.0.0.1:8000/docs>. Try `GET /api/health` → `"database": "ok"`.
Click **Authorize**, log in with the admin phone number and password, then try `GET /api/auth/profile`.

---

## Step 7 — Run the frontend

Open a **second** terminal (keep uvicorn running):

```powershell
cd path\to\krishimitra\frontend
npm install
npm test          # expect: 17 passed
npm run dev
```

Open <http://localhost:5173>, register a farmer account, and look around.
The microphone and camera only work on `localhost` or HTTPS, which is a browser rule.

---

## Step 8 — First real AI requests (downloads models once)

The first time you use each feature, models download into `trained_models\cache` (needs internet):

| Feature | Model | Download |
| --- | --- | --- |
| Speech recognition | Faster-Whisper small | ~470 MB |
| Translation | NLLB-200 distilled 600M | ~2.5 GB |
| Embeddings | all-MiniLM-L6-v2 | ~90 MB |
| Reranking | FlashRank MiniLM-L-12 | ~35 MB |

To download everything at startup instead, set `PRELOAD_MODELS=true` in `.env` (startup takes a few minutes).

1. **Add knowledge:** log in as admin → *Documents* → upload 3–5 PDFs (see `knowledge_base/SOURCES.md`).
   Wait until each shows `indexed`.
2. **Ask:** farmer account → *Voice assistant* → type or speak a question about those PDFs.
3. **Disease model:** train it on Colab (`ml/disease_detection/notebooks/disease_detection_colab.ipynb`) and copy
   `disease_model.onnx` and `disease_labels.json` into `trained_models\`. Restart uvicorn.

---

## Common errors and fixes

| Error | Cause | Fix |
| --- | --- | --- |
| `connection refused ... port 5432` | PostgreSQL is not running | Start → Services → `postgresql-x64-16` → Start |
| `password authentication failed for user "krishimitra"` | Wrong password in `DATABASE_URL` | Fix `.env`; special characters like `@` must be URL-encoded (`@` → `%40`) |
| `Field required ... JWT_SECRET_KEY` | `.env` missing or not in `backend\` | Run commands from inside `backend\`; check the file name is `.env`, not `.env.txt` |
| `ffmpeg is not installed or not on PATH` | FFmpeg missing | `winget install Gyan.FFmpeg`, reopen terminal |
| `Translation model is not available` | First download failed (no internet, or disk full) | Check internet and free space (need ~5 GB); retry |
| `Gemini rejected the API key` | Wrong or restricted key | Create a new key in AI Studio; no spaces in `.env` |
| `Gemini model '...' was not found` | Model name changed | Set `GEMINI_MODEL` to a current name from <https://ai.google.dev/gemini-api/docs/models> |
| `OpenWeather rejected the API key` | New keys take up to ~2 hours | Wait, then retry |
| `Disease model not found` (503) | Model not trained yet | Train on Colab, copy the two files into `trained_models\` |
| Microphone button does nothing | Browser blocked mic | Click the lock icon in the address bar → allow microphone |
| `npm ERR! code ENOENT` | Ran npm outside `frontend\` | `cd frontend` first |
| Very slow first answer | Models loading for the first time | Normal; later answers are faster. Or set `PRELOAD_MODELS=true` |
| `MemoryError` / PC freezes | 8 GB RAM with all models | Use `WHISPER_MODEL_SIZE=base` and the CTranslate2 int8 NLLB (see `nllb_translator.py` docstring) |
