"""Seed / update reference data: languages, intents and disease information.

Safe to run many times (it updates existing rows).
    cd backend
    python -m scripts.seed_data
"""
import json
from pathlib import Path

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import Disease, Intent, Language
from app.services.translation.languages import DEFAULT_LANGUAGES, INTENTS

DISEASE_FILE = Path(__file__).resolve().parents[1] / "app" / "data" / "disease_info.json"


def upsert(db, model, key: str, rows: list[dict]) -> tuple[int, int]:
    created = updated = 0
    for row in rows:
        existing = db.scalars(select(model).where(getattr(model, key) == row[key])).first()
        if existing:
            for field, value in row.items():
                setattr(existing, field, value)
            updated += 1
        else:
            db.add(model(**row))
            created += 1
    return created, updated


def main() -> None:
    db = SessionLocal()
    try:
        c, u = upsert(db, Language, "code", DEFAULT_LANGUAGES)
        print(f"languages: {c} created, {u} updated")
        c, u = upsert(db, Intent, "name", [{"name": n, "description": d} for n, d in INTENTS])
        print(f"intents:   {c} created, {u} updated")
        data = json.loads(DISEASE_FILE.read_text(encoding="utf-8"))["diseases"]
        rows = [{"is_healthy": False, **d} for d in data]
        c, u = upsert(db, Disease, "class_label", rows)
        print(f"diseases:  {c} created, {u} updated")
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    main()
