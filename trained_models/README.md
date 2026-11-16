# trained_models/

The backend loads model files from here. This folder starts empty; nothing here is committed to Git.

| File | Produced by | Without it |
| --- | --- | --- |
| `disease_model.onnx`, `disease_labels.json` | `ml/disease_detection/src/export_onnx.py` (Colab notebook) | Disease page returns "model not found" (503) |
| `intent_model.joblib` | `ml/intent_classification/train_intent.py` (only if it beats keyword rules) | Keyword rules are used (shown in admin System status) |
| `cache/` | Downloaded automatically on first use (Whisper, NLLB, MiniLM, FlashRank) | Downloaded when first needed |
| `nllb-600m-ct2-int8/` (optional) | `ct2-transformers-converter` (see `nllb_translator.py`) | Standard NLLB is used |
