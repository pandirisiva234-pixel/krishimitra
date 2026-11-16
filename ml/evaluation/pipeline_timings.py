"""NFR-1 — End-to-end latency per pipeline stage, from real requests stored in PostgreSQL.

Every answer saves its stage timings (responses.timings_ms). After using the app
(or running a scripted test session), summarise them:

    python pipeline_timings.py --out results/latency
"""
import argparse
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
from app.db.session import engine  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="results/latency", type=Path)
    ap.add_argument("--days", type=int, default=30)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    sql = text("""
        SELECT r.timings_ms, q.input_mode, l.code AS language, i.name AS intent
        FROM responses r JOIN queries q ON q.id = r.query_id
        JOIN languages l ON l.id = q.language_id LEFT JOIN intents i ON i.id = q.intent_id
        WHERE q.created_at >= now() - make_interval(days => :days)
    """)
    with engine.connect() as conn:
        rows = conn.execute(sql, {"days": args.days}).mappings().all()
    if not rows:
        raise SystemExit("No answers recorded yet.")
    df = pd.json_normalize([{**r["timings_ms"], "input_mode": r["input_mode"], "language": r["language"],
                             "intent": r["intent"]} for r in rows])
    stages = [c for c in df.columns if c not in ("input_mode", "language", "intent")]
    summary = df[stages].describe(percentiles=[0.5, 0.95]).T[["count", "mean", "50%", "95%", "max"]].round(0)
    summary.to_csv(args.out / "stage_latency_ms.csv")
    print(summary.to_string())
    by_lang = df.groupby("language")["total"].describe(percentiles=[0.5, 0.95]).round(0)
    by_lang.to_csv(args.out / "total_latency_by_language_ms.csv")
    print(by_lang.to_string())


if __name__ == "__main__":
    main()
