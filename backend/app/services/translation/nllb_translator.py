"""Translation with Meta's NLLB-200.

Two backends (set NLLB_BACKEND in .env):
- "transformers": loads facebook/nllb-200-distilled-600M with PyTorch (simplest).
- "ctranslate2":  loads an int8-converted copy (about 4x less RAM, faster on CPU).
  Create it once with:  python scripts/get_fast_translator.py
  (NLLB_BACKEND=auto, the default, then picks it up automatically.)

Long text is split into sentences because NLLB is trained on sentence pairs and
quality drops on long paragraphs.
"""
import logging
import re
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

# Split after ., !, ?, the Devanagari danda (।) or a newline
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?।])(?<!\b\d\.)(?<!\b\d\d\.)\s+|\n+")  # not after "1." / "12."


NO_REPEAT_NGRAM = 4  # stops repetition loops without blocking normal repeated words


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_SPLIT.split(text) if s and s.strip()]


class Translator:
    def __init__(self, model_name: str, backend: str, cache_dir: Path, ct2_path: str | None = None, beam_size: int = 2):
        self.model_name = model_name
        # "auto": use the int8 CTranslate2 copy when its folder exists, otherwise PyTorch
        if backend == "auto":
            backend = "ctranslate2" if ct2_path and (Path(ct2_path) / "model.bin").exists() else "transformers"
        self.backend = backend
        self.beam_size = beam_size
        self.cache_dir = cache_dir
        self.ct2_path = ct2_path
        self._tokenizer = None
        self._model = None
        self._lock = threading.Lock()

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    def _load(self):
        if self._model is not None:
            return
        with self._lock:
            if self._model is not None:
                return
            from transformers import AutoTokenizer

            cache = str(self.cache_dir / "huggingface")
            self._tokenizer = AutoTokenizer.from_pretrained(self.model_name, cache_dir=cache)
            if self.backend == "ctranslate2":
                import ctranslate2

                if not self.ct2_path:
                    raise RuntimeError("NLLB_BACKEND=ctranslate2 needs NLLB_CT2_PATH")
                logger.info("Loading NLLB (CTranslate2 int8) from %s", self.ct2_path)
                self._model = ctranslate2.Translator(self.ct2_path, device="cpu", compute_type="int8")
            else:
                from transformers import AutoModelForSeq2SeqLM

                logger.info("Loading NLLB '%s' (transformers)", self.model_name)
                self._model = AutoModelForSeq2SeqLM.from_pretrained(self.model_name, cache_dir=cache)
                self._model.eval()

    def translate(self, text: str, src_lang: str, tgt_lang: str, max_length: int = 400) -> str:
        """Translate between NLLB codes, e.g. src_lang="tel_Telu", tgt_lang="eng_Latn".

        Every sentence of every line is translated in ONE batch (much faster than one call per
        line), then put back in place so numbered steps and paragraphs keep their line breaks.
        """
        if not text.strip() or src_lang == tgt_lang:
            return text
        lines = [split_sentences(line) if line.strip() else [] for line in text.split("\n")]
        sentences = [s for line in lines for s in line]
        if not sentences:
            return text
        translated = iter(self._translate_sentences(sentences, src_lang, tgt_lang, max_length))
        out_lines = []
        for line in lines:
            kept: list[str] = []
            for _ in line:
                sent = next(translated)
                if sent and sent in kept:  # NLLB sometimes repeats a sentence; keep it once
                    continue
                kept.append(sent)
            out_lines.append(" ".join(kept))
        return "\n".join(out_lines)

    def _translate_sentences(self, sentences: list[str], src_lang: str, tgt_lang: str, max_length: int) -> list[str]:
        self._load()
        self._tokenizer.src_lang = src_lang
        if self.backend == "ctranslate2":
            tokens = [self._tokenizer.convert_ids_to_tokens(self._tokenizer.encode(s)) for s in sentences]
            # NLLB sometimes falls into a loop ("cattle cattle cattle ..."). Two guards:
            # never repeat the same 4-token sequence, and cap the output at ~3x the input length.
            limit = min(max_length, 3 * max(len(t) for t in tokens) + 10)
            results = self._model.translate_batch(
                tokens, target_prefix=[[tgt_lang]] * len(tokens), beam_size=self.beam_size,
                max_decoding_length=limit, max_batch_size=16, no_repeat_ngram_size=NO_REPEAT_NGRAM,
            )
            outputs = []
            for r in results:
                out_tokens = r.hypotheses[0][1:]  # drop the language tag
                outputs.append(self._tokenizer.decode(self._tokenizer.convert_tokens_to_ids(out_tokens)))
        else:
            import torch

            inputs = self._tokenizer(sentences, return_tensors="pt", padding=True, truncation=True, max_length=512)
            limit = min(max_length, 3 * int(inputs["input_ids"].shape[1]) + 10)
            with torch.inference_mode():
                generated = self._model.generate(
                    **inputs,
                    forced_bos_token_id=self._tokenizer.convert_tokens_to_ids(tgt_lang),
                    max_length=limit,
                    num_beams=self.beam_size,
                    no_repeat_ngram_size=NO_REPEAT_NGRAM,
                )
            outputs = self._tokenizer.batch_decode(generated, skip_special_tokens=True)
        return [o.strip() for o in outputs]
