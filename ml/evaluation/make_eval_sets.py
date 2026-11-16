"""Turn the one evaluation sheet you fill in into the three test files.

    cd ml/evaluation
    python make_eval_sets.py            # reads data/eval_sheet.csv

eval_sheet.csv columns:
  id, language, question, english_reference, relevant, audio_file
  - question           the farmer question in Telugu (read it aloud for the recording)
  - english_reference  YOUR English translation of the question (not a machine's)
  - relevant           a word that must appear in the correct document passage, e.g. "thrips|Scirtothrips"
  - audio_file         your recording of the question, e.g. recordings/te_01.m4a

Writes data/stt_manifest.csv, data/translation_testset.csv and data/rag_questions.csv,
skipping rows where the needed column is still empty.
"""
from pathlib import Path

import pandas as pd

DATA = Path(__file__).resolve().parent / "data"


def main() -> None:
    sheet = pd.read_csv(DATA / "eval_sheet.csv", dtype=str, encoding="utf-8-sig").fillna("")
    sheet = sheet.apply(lambda c: c.str.strip())
    has_audio = sheet.audio_file.ne("") & sheet.audio_file.map(lambda p: (DATA / p).exists() if p else False)
    stt = sheet[has_audio][["audio_file", "language", "question"]]
    stt.columns = ["audio_path", "language", "reference"]
    tr = sheet[sheet.english_reference.ne("")][["language", "question", "english_reference"]]
    tr.columns = ["language", "source", "reference_en"]
    rag = sheet[sheet.english_reference.ne("") & sheet.relevant.ne("")][
        ["question", "language", "english_reference", "relevant"]]
    rag.columns = ["question", "language", "question_en", "relevant"]
    for name, df in (("stt_manifest", stt), ("translation_testset", tr), ("rag_questions", rag)):
        df.to_csv(DATA / f"{name}.csv", index=False, encoding="utf-8")
        print(f"{name}.csv: {len(df)} rows")
    missing = sheet[sheet.audio_file.ne("") & ~has_audio].audio_file.tolist()
    if missing:
        print("Recordings not found (check names):", ", ".join(missing))


if __name__ == "__main__":
    main()
