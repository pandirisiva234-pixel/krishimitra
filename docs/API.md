# REST API

Interactive documentation with "Try it out": **http://127.0.0.1:8000/docs** (Swagger) or `/redoc`.
All endpoints are under `/api`. Protected endpoints need `Authorization: Bearer <token>` from login.

Every error has the same shape:
```json
{"error": {"code": "validation_error", "message": "Invalid input", "request_id": "a1b2c3", "details": [...]}}
```

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| GET | `/health` | – | Server and database status |
| GET | `/languages` | – | Active languages |
| POST | `/auth/register` | – (5/min) | Create farmer account; returns token |
| POST | `/auth/login` | – (5/min) | Form fields `username` (phone or email), `password`; returns token |
| POST | `/auth/logout` | user | Client discards token |
| GET | `/auth/profile` | user | Current user |
| PUT | `/auth/profile` | user | Update name, email, language, location, crops |
| POST | `/auth/change-password` | user | Change password |
| POST | `/voice/transcribe` | user (20/min) | Multipart `audio` (≤60 s, ≤10 MB) → text, language, `audio_id` |
| POST | `/assistant/query` | user (20/min) | `{text, language_code?, conversation_id?, input_mode, audio_id?, speak}` → answer, sources, intent, timings, audio URL |
| POST | `/assistant/speak` | user (20/min) | `{text, language_code, translate_from_english}` → audio URL |
| GET | `/assistant/audio/{file}` | user | MP3 of a spoken answer |
| POST | `/feedback` | user | `{response_id, is_helpful, comment?}` (once per answer) |
| POST | `/disease/predict` | user (20/min) | Multipart `image` (≤5 MB) → label, confidence, top-3, treatment |
| GET | `/disease/history` | user | Own predictions |
| GET | `/disease/classes` | user | Disease library |
| GET | `/disease/images/{file}` | owner/admin | Uploaded leaf photo |
| GET | `/weather/current` | user | `lat`, `lon` (default: profile location) |
| GET | `/weather/forecast` | user | 5-day forecast, daily summary, advisories |
| GET | `/weather/geocode` | user | `q` = place name → coordinates |
| POST | `/knowledge/upload` | admin | Multipart `file`, `title`, `source_url?` → indexing in background |
| GET | `/knowledge/documents` | user | All documents with status |
| DELETE | `/knowledge/documents/{id}` | admin | Delete document, file and vectors |
| POST | `/knowledge/search` | user | `{query, language_code?, top_n}` → passages |
| GET | `/conversations` | user | Own conversations |
| GET | `/conversations/{id}` | owner | Conversation with all messages |
| DELETE | `/conversations/{id}` | owner | Delete conversation |
| GET | `/dashboard/summary` | user | Farmer dashboard numbers |
| GET | `/admin/dashboard` | admin | Totals |
| GET | `/admin/statistics` | admin | `days` → language, intent, disease, per-day, input-mode stats |
| GET | `/admin/users` | admin | `search`, `role`, `page`, `page_size` |
| PATCH | `/admin/users/{id}` | admin | `{is_active?, role?}` |
| GET | `/admin/system` | admin | DB, vector store, API keys, models, disk |

## Status codes used

`200` OK · `201` created · `202` accepted (indexing started) · `400` bad file/input · `401` not logged in or token
expired · `403` not allowed (e.g. farmer on admin route) · `404` not found or not yours · `409` duplicate ·
`422` validation error · `429` rate limit · `502` external service failed · `503` feature not configured (missing
key or model).

## Example: ask a question with curl (PowerShell: use `curl.exe`)

```bash
TOKEN=$(curl -s -X POST localhost:8000/api/auth/login -d "username=9876543210&password=Farmer123" | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
curl -s -X POST localhost:8000/api/assistant/query -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" -d '{"text":"వరి పంటకు ఎరువు ఎప్పుడు వేయాలి?","speak":true}'
```
