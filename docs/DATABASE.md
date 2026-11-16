# Database design (PostgreSQL)

12 tables, created by `alembic upgrade head`. ChromaDB is separate and stores only text chunks and vectors;
each vector carries the PostgreSQL `documents.id` so both stay in sync (deleting a document deletes its vectors).

## ER diagram

Rendered image for the report: [er_diagram.png](er_diagram.png). The source is below; GitHub and VS Code (with a Mermaid extension) render it.

```mermaid
erDiagram
    languages ||--o{ users : "preferred by"
    users ||--o| admins : "has admin profile"
    users ||--o{ conversation_history : owns
    languages ||--o{ conversation_history : "answered in"
    conversation_history ||--o{ queries : contains
    users ||--o{ queries : asks
    languages ||--o{ queries : "asked in"
    intents ||--o{ queries : classifies
    queries ||--|| responses : "answered by"
    responses ||--o{ feedback : receives
    users ||--o{ feedback : gives
    users ||--o{ disease_predictions : makes
    diseases ||--o{ disease_predictions : "identified as"
    users ||--o{ documents : uploads
    users ||--o{ weather_data : requests

    languages {
        int id PK
        string code UK
        string nllb_code
        string whisper_code
        string tts_voice
        string script
        bool is_active
    }
    users {
        int id PK
        string phone UK
        string email UK
        string password_hash
        string role
        int preferred_language_id FK
        float latitude
        float longitude
        bool is_active
    }
    admins {
        int id PK
        int user_id FK, UK
        string designation
        bool can_manage_users
        bool can_manage_documents
    }
    intents {
        int id PK
        string name UK
        string description
    }
    conversation_history {
        int id PK
        int user_id FK
        int language_id FK
        string title
        timestamp updated_at
    }
    queries {
        int id PK
        int conversation_id FK
        int user_id FK
        int language_id FK
        int intent_id FK
        string input_mode
        text original_text
        text english_text
        float language_confidence
        float intent_confidence
        string audio_path
        float audio_duration_sec
    }
    responses {
        int id PK
        int query_id FK, UK
        text answer_english
        text answer_text
        bool grounded
        jsonb sources
        string model_name
        string audio_path
        jsonb timings_ms
        int total_ms
    }
    feedback {
        int id PK
        int response_id FK
        int user_id FK
        bool is_helpful
        string comment
    }
    diseases {
        int id PK
        string class_label UK
        string crop
        string disease_name
        bool is_healthy
        text treatment
        text prevention
    }
    disease_predictions {
        int id PK
        int user_id FK
        int disease_id FK
        string predicted_label
        float confidence
        bool is_uncertain
        jsonb top_predictions
        float blur_score
        string image_path
    }
    documents {
        int id PK
        string title
        string stored_path
        int num_pages
        int num_chunks
        string status
        int uploaded_by FK
    }
    weather_data {
        int id PK
        int user_id FK
        string kind
        float latitude
        float longitude
        jsonb payload
        timestamp fetched_at
    }
```

## Design decisions (for the report)

| Decision | Reason |
| --- | --- |
| Role column on `users` + separate `admins` table | Access is checked from one column (simple, fast); the spec's `admins` table holds admin-only details without nullable columns on every farmer row |
| `queries` and `responses` separate, 1:1 | A question exists even if answering fails; responses carry model output, sources and timings, which are analysed separately |
| `conversation_history` groups queries | Lets farmers continue a conversation and see history by topic |
| `languages` as a table, not an enum | Adding a language needs only a row, no code or migration |
| JSONB for `sources`, `timings_ms`, `top_predictions`, weather `payload` | Variable-shape data that is read whole; still queryable in PostgreSQL |
| `ON DELETE CASCADE` from users | Deleting an account removes all personal data (privacy) |
| `ON DELETE SET NULL` for intents/diseases | Reference data changes never delete history |
| CHECK constraints (role, input_mode, status, kind) | Invalid values are rejected by the database itself |
| Indexes on every foreign key and `fetched_at` | Dashboard and statistics queries stay fast as data grows |
| Unique (`response_id`, `user_id`) on feedback | One rating per answer per farmer |

## Useful commands

```powershell
alembic upgrade head                         # apply migrations
alembic downgrade -1                         # undo the last migration
alembic revision --autogenerate -m "message" # after changing a model
psql -U krishimitra -d krishimitra -c "\d queries"   # inspect a table
```
