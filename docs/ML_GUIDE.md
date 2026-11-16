# ML research guide (Phases 7–9, 12–14)

Everything here produces files in `results/` folders. Report only numbers from those files.

## 1. Plant disease detection (research component)

**Datasets**

| Dataset | Use | Why |
| --- | --- | --- |
| PlantVillage (Kaggle: `abdallahalidev/plantvillage-dataset`, "color" folder) | Train / validation / test | Large, labelled, 38 classes, widely cited, so results can be compared with papers |
| PlantDoc (GitHub: `pratikkayal/PlantDoc-Dataset`) | Independent field test only | Real field photos. PlantVillage images have plain lab backgrounds, so its test accuracy overstates field performance |

> Important for your crops: PlantVillage covers tomato, potato, pepper, maize, grape, apple and others, but **not
> paddy, cotton, chilli or groundnut**. To support those, add a public dataset for each (search Kaggle for
> "rice leaf disease" and "cotton leaf disease"), put its class folders next to the PlantVillage ones, add their
> entries to `backend/app/data/disease_info.json`, and re-run the steps below. Say clearly in the report which
> crops the final model covers.

**Run on Colab** (GPU): open `ml/disease_detection/notebooks/disease_detection_colab.ipynb`. It runs, in order:

| Step | Script | Output you put in the report |
| --- | --- | --- |
| Cleaning + split | `prepare_split.py` | `results/eda/cleaning_report.json`, `class_distribution.png`, split sizes |
| Exploration | `eda.py` | `image_stats.json`, `sample_grid.png` |
| Tuning (optional) | `tune.py` | `results/tuning_<model>.csv` |
| Training ×4 | `train.py` | `results/<model>/curves.png`, `history.json` |
| Test evaluation | `evaluate.py --tag test` | `metrics_test.json`, `confusion_matrix_test.png`, `classification_report_test.csv` |
| Comparison | `compare.py` | `comparison_test.md` / `.png` (accuracy vs speed vs size) |
| Field evaluation | `prepare_external.py`, `evaluate.py --tag field` | `comparison_field.md`: the honest real-world number |
| Export | `export_onnx.py` | `trained_models/disease_model.onnx`, `disease_labels.json`, ONNX = PyTorch check |

**Method summary for the report:** stratified 70/15/15 split with a fixed seed; inverse-frequency class
weights and label smoothing; augmentation (crop, flip, rotation, colour jitter, blur) to imitate field photos;
transfer learning in two stages (frozen backbone, then fine-tuning at 10× lower learning rate); early stopping
on validation loss; model selection on validation, final numbers on the untouched test set; macro-averaged
precision/recall/F1 because classes are imbalanced; CPU latency measured because the app runs on CPU.

**Pick the deployed model** by macro-F1 on the field test, then latency. Write down why.

## 2. Intent classification

```powershell
cd ml\intent_classification
python train_intent.py --data data\intents_seed.csv
```

It compares TF-IDF + logistic regression, MiniLM embeddings + logistic regression, and the backend's keyword
rules on the same held-out 20%. It saves a model **only if** it beats the keyword rules.

On the 240-question development set (run on 13 Nov 2026, TF-IDF only, because the embedding model could not be
downloaded in that environment): TF-IDF macro-F1 0.56 vs keyword rules 0.76 on 48 test questions, so no model was
saved and the app uses the keyword rules. **These numbers come from a small, author-written set and must not be
reported as final.** Collect at least 600 real questions (your own recordings, or a public Kisan Call Centre
query dataset if you can access one), relabel, and re-run with the embedding model.

## 3. Speech, translation and retrieval (research questions RQ1–RQ3)

Create the test sets described in `ml/evaluation/data/README.md`, then:

```powershell
cd ml\evaluation
python stt_eval.py --manifest data\stt_manifest.csv --models small medium     # RQ1: WER/CER per language
python translation_eval.py --data data\translation_testset.csv                 # chrF++ both directions
python rag_eval.py --questions data\rag_questions.csv                          # RQ2 + RQ3: hit@k, MRR
python pipeline_timings.py                                                     # NFR-1: latency per stage
```

## 4. Reporting rules

1. Every number in the report points to a file in a `results/` folder.
2. State dataset, split, number of test items and date next to each table.
3. Report failures and limits (field accuracy drop, weak languages, small test sets) as findings, not omissions.
4. Never tune on the test set.
