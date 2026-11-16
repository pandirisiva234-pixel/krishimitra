"""Translation with AI4Bharat's IndicTrans2 (IIT Madras), distilled 200M models.

IndicTrans2 is trained only on English <-> the 22 scheduled Indian languages, so on farming text it
usually keeps Indian words better than Meta's NLLB (trained on 200 languages). It uses the same
language codes as NLLB (tel_Telu, kan_Knda, ...), so nothing else in the app changes.

Two models: en-indic (answers) and indic-en (questions), about 1 GB together, MIT licence.
They are gated on Hugging Face: log in, click "Agree" on both model pages, and put a read token
in backend/.env as HF_TOKEN. Set it up and test it with:  python scripts/get_indictrans2.py
Then set TRANSLATION_ENGINE=indictrans2 in .env. If it cannot load, the app uses NLLB instead.
"""
import logging
import re
import threading
import unicodedata
from pathlib import Path

from app.services.translation.nllb_translator import split_sentences

logger = logging.getLogger(__name__)

EN_INDIC = "ai4bharat/indictrans2-en-indic-dist-200M"
INDIC_EN = "ai4bharat/indictrans2-indic-en-dist-200M"
ENGLISH = "eng_Latn"


_ISO = {"eng_Latn": "en", "tel_Telu": "te", "kan_Knda": "kn", "hin_Deva": "hi", "mar_Deva": "mr",
        "ben_Beng": "bn", "guj_Gujr": "gu", "mal_Mlym": "ml", "tam_Taml": "ta", "urd_Arab": "ur",
        "pan_Guru": "pa", "ory_Orya": "or", "asm_Beng": "as"}
_NO_TRANSLIT = {"Arab", "Aran", "Olck", "Mtei", "Latn"}
_FULL_STOP_LANGS = {"te", "kn", "ta", "ml", "gu"}


class IndicNLPProcessor:
    """The same steps as AI4Bharat's IndicTransToolkit, in pure Python (that package has no Windows build
    and breaks with new transformers versions).

    IndicTrans2 was trained with every Brahmic script (Telugu, Kannada, ...) written in Devanagari letters,
    so the input is transliterated to Devanagari and the output back to the farmer's script. Text is
    normalised and tokenised the way the model saw it in training (indic-nlp-library, Moses for English).
    """

    def __init__(self):
        from indicnlp.normalize.indic_normalize import IndicNormalizerFactory
        from indicnlp.tokenize import indic_detokenize, indic_tokenize
        from indicnlp.transliterate.unicode_transliterate import UnicodeIndicTransliterator
        from sacremoses import MosesDetokenizer, MosesPunctNormalizer, MosesTokenizer

        self._factory = IndicNormalizerFactory()
        self._normalizers: dict = {}
        self._tok, self._detok = indic_tokenize, indic_detokenize
        self._xlit = UnicodeIndicTransliterator
        self._punc = MosesPunctNormalizer()
        self._en_tok, self._en_detok = MosesTokenizer(lang="en"), MosesDetokenizer(lang="en")

    def _normalizer(self, iso: str):
        if iso not in self._normalizers:
            try:
                self._normalizers[iso] = self._factory.get_normalizer(iso)
            except Exception:  # noqa: BLE001  - e.g. Urdu needs an extra package; skip normalising
                self._normalizers[iso] = None
        return self._normalizers[iso]

    def _pre(self, sent: str, src_lang: str, tgt_lang: str) -> str:
        iso, script = _ISO.get(src_lang, "hi"), src_lang.split("_")[1]
        sent = self._punc.normalize(unicodedata.normalize("NFC", sent.strip()))
        if iso == "en":
            text = " ".join(self._en_tok.tokenize(sent, escape=False))
        else:
            norm = self._normalizer(iso)
            if norm is not None:
                sent = norm.normalize(sent)
            text = " ".join(self._tok.trivial_tokenize(sent, iso))
            if script not in _NO_TRANSLIT:
                text = self._xlit.transliterate(text, iso, "hi")
        return f"{src_lang} {tgt_lang} {text.strip()}"

    def _post(self, sent: str, lang: str) -> str:
        if lang == "eng_Latn":
            return self._en_detok.detokenize(sent.split(" "))
        iso, script = _ISO.get(lang, "hi"), lang.split("_")[1]
        if script in ("Arab", "Aran"):
            sent = sent.replace(" ؟", "؟").replace(" ۔", "۔").replace(" ،", "،")
        elif script not in _NO_TRANSLIT:
            sent = self._xlit.transliterate(sent, "hi", iso)
            if iso in _FULL_STOP_LANGS:  # these scripts end sentences with ".", not the Hindi danda
                sent = sent.replace("।", ".")
        return self._detok.trivial_detokenize(sent, iso)

    def preprocess_batch(self, sentences, src_lang, tgt_lang):
        return [self._pre(s, src_lang, tgt_lang) for s in sentences]

    def postprocess_batch(self, sentences, lang):
        return [self._post(s, lang).strip() for s in sentences]


def _processor():
    return IndicNLPProcessor()


def _install_compat_shims() -> None:
    """IndicTrans2's model code was written for transformers 4.x. Its config file imports
    transformers.onnx, which transformers 5 removed; it only uses it for ONNX export, so empty
    stand-ins are enough."""
    import importlib.util
    import sys
    import types

    if "transformers.onnx" in sys.modules:  # real module, or our stand-in from an earlier model load
        return
    try:
        if importlib.util.find_spec("transformers.onnx") is not None:
            return
    except (ModuleNotFoundError, ValueError):
        pass

    class OnnxConfig:  # noqa: D401 - placeholder
        pass

    class OnnxSeq2SeqConfigWithPast(OnnxConfig):
        pass

    onnx = types.ModuleType("transformers.onnx")
    onnx.OnnxConfig, onnx.OnnxSeq2SeqConfigWithPast = OnnxConfig, OnnxSeq2SeqConfigWithPast
    utils = types.ModuleType("transformers.onnx.utils")
    utils.compute_effective_axis_dimension = lambda dimension, fixed_dimension, num_token_to_add=0: (
        fixed_dimension if dimension <= 0 else dimension)
    sys.modules.setdefault("transformers.onnx", onnx)
    sys.modules.setdefault("transformers.onnx.utils", utils)


def _compatible(cls):
    """Give the old model class what transformers 5 expects: generate() via GenerationMixin and a
    tie_weights() that accepts new keyword arguments (IndicTrans2 ties no weights anyway)."""
    from transformers import GenerationMixin

    bases = (cls,) if issubclass(cls, GenerationMixin) else (cls, GenerationMixin)
    return type(cls.__name__, bases, {"tie_weights": lambda self, *args, **kwargs: None})


def _rebuild_position_tables(model) -> None:
    """The sinusoidal position tables are not stored in the weights file. transformers 5 builds the
    model on an empty device first, so they come out as garbage (even NaN): compute them again."""
    for module in model.modules():
        if hasattr(module, "get_embedding") and hasattr(module, "weights") and hasattr(module, "embedding_dim"):
            module.weights = module.get_embedding(
                module.weights.shape[0], module.embedding_dim, module.padding_idx
            ).to(module.weights.device)


class IndicTransTokenizer:
    """Reads IndicTrans2's own vocabulary files directly.

    AI4Bharat's tokenizer class sets attributes before the base class is ready, which transformers 5
    no longer allows. The format is simple, so this does the same job without it:
      input  = [source-language tag, target-language tag] + SentencePiece pieces of the text + </s>
      output = pieces from the target vocabulary, joined with SentencePiece spaces (U+2581).
    Files (downloaded with the model): dict.SRC.json, dict.TGT.json (piece -> id), model.SRC, model.TGT.
    """

    SPECIAL = ("<s>", "<pad>", "</s>", "<unk>")

    def __init__(self, files: dict[str, str], max_length: int = 256):
        import json

        import sentencepiece as spm

        with open(files["dict.SRC.json"], encoding="utf-8") as f:
            self.src_vocab = json.load(f)
        with open(files["dict.TGT.json"], encoding="utf-8") as f:
            self.tgt_vocab = json.load(f)
        self.tgt_rev = {i: t for t, i in self.tgt_vocab.items()}
        self.src_spm = spm.SentencePieceProcessor(model_file=files["model.SRC"])
        self.max_length = max_length
        self.pad_id = self.src_vocab.get("<pad>", 1)
        self.eos_id = self.src_vocab.get("</s>", 2)
        self.unk_id = self.src_vocab.get("<unk>", 3)
        self.tgt_special_ids = {self.tgt_vocab[t] for t in self.SPECIAL if t in self.tgt_vocab}

    def encode_batch(self, tagged: list[str]):
        """tagged: "src_tag tgt_tag text" strings from the processor. Returns padded tensors."""
        import torch

        rows = []
        for line in tagged:
            src_tag, tgt_tag, text = line.split(" ", 2)
            pieces = [src_tag, tgt_tag] + self.src_spm.encode(text, out_type=str)
            ids = [self.src_vocab.get(p, self.unk_id) for p in pieces][: self.max_length - 1] + [self.eos_id]
            rows.append(ids)
        width = max(len(r) for r in rows)
        input_ids = torch.full((len(rows), width), self.pad_id, dtype=torch.long)
        mask = torch.zeros((len(rows), width), dtype=torch.long)
        for i, r in enumerate(rows):
            input_ids[i, : len(r)] = torch.tensor(r)
            mask[i, : len(r)] = 1
        return {"input_ids": input_ids, "attention_mask": mask}

    def decode_batch(self, sequences) -> list[str]:
        out = []
        for seq in sequences:
            pieces = [self.tgt_rev.get(int(i), "") for i in seq if int(i) not in self.tgt_special_ids]
            out.append("".join(pieces).replace("\u2581", " ").strip())
        return out


_VISARGA = re.compile(r"[\u0903\u0983\u0A83\u0B03\u0C03\u0C83\u0D03](?=\s|$)")


def _restore_colons(source: str, translated: str) -> str:
    """IndicTrans2 writes a colon as the visarga letter (ः / ಃ / ః), e.g. "Problem:" -> "ಸಮಸ್ಯೆಃ".
    For every colon in the source sentence, turn the first visarga that ends a word back into ":"."""
    for _ in range(source.count(":")):
        translated, n = _VISARGA.subn(":", translated, count=1)
        if not n:
            break
    return translated


class IndicTransTranslator:
    def __init__(self, cache_dir: Path, hf_token: str | None = None, beam_size: int = 2, max_length: int = 256):
        self.cache_dir = cache_dir
        self.hf_token = hf_token
        self.beam_size = beam_size
        self.max_length = max_length
        self.model_name = "IndicTrans2-dist-200M"
        self._models: dict[str, tuple] = {}
        self._ip = None
        self._lock = threading.Lock()

    @property
    def is_loaded(self) -> bool:
        return len(self._models) == 2

    def _load_one(self, name: str):
        if name in self._models:
            return self._models[name]
        with self._lock:
            if name not in self._models:
                from transformers import AutoConfig
                from transformers.dynamic_module_utils import get_class_from_dynamic_module

                _install_compat_shims()
                cache = str(self.cache_dir / "huggingface")
                kw = dict(trust_remote_code=True, cache_dir=cache, token=self.hf_token)
                logger.info("Loading %s", name)
                config = AutoConfig.from_pretrained(name, **kw)
                if "vocab_size" not in config.__dict__:  # newer transformers read config.vocab_size
                    config.vocab_size = config.decoder_vocab_size
                cls = get_class_from_dynamic_module(config.auto_map["AutoModelForSeq2SeqLM"], name,
                                                    cache_dir=cache, token=self.hf_token)
                model = _compatible(cls).from_pretrained(name, config=config, cache_dir=cache, token=self.hf_token)
                _rebuild_position_tables(model)
                model.eval()
                from huggingface_hub import hf_hub_download

                files = {f: hf_hub_download(name, f, cache_dir=cache, token=self.hf_token)
                         for f in ("dict.SRC.json", "dict.TGT.json", "model.SRC", "model.TGT")}
                tok = IndicTransTokenizer(files)
                self._models[name] = (tok, model)
                if self._ip is None:
                    self._ip = _processor()
        return self._models[name]

    def _load(self):
        self._load_one(EN_INDIC)
        self._load_one(INDIC_EN)

    def translate(self, text: str, src_lang: str, tgt_lang: str, max_length: int = 400) -> str:
        """Same behaviour as the NLLB Translator: sentences in one batch, line breaks kept."""
        if not text.strip() or src_lang == tgt_lang:
            return text
        if ENGLISH not in (src_lang, tgt_lang):  # Indian -> Indian: go through English
            return self.translate(self.translate(text, src_lang, ENGLISH), ENGLISH, tgt_lang)
        lines = [split_sentences(line) if line.strip() else [] for line in text.split("\n")]
        sentences = [s for line in lines for s in line]
        if not sentences:
            return text
        translated = iter(self._translate_sentences(sentences, src_lang, tgt_lang))
        out_lines = []
        for line in lines:
            kept: list[str] = []
            for _ in line:
                sent = next(translated)
                if sent and sent in kept:
                    continue
                kept.append(sent)
            out_lines.append(" ".join(kept))
        return "\n".join(out_lines)

    def _translate_sentences(self, sentences: list[str], src_lang: str, tgt_lang: str) -> list[str]:
        import torch

        tok, model = self._load_one(EN_INDIC if src_lang == ENGLISH else INDIC_EN)
        batch = self._ip.preprocess_batch(sentences, src_lang=src_lang, tgt_lang=tgt_lang)
        inputs = tok.encode_batch(batch)
        limit = min(self.max_length, 3 * int(inputs["input_ids"].shape[1]) + 10)
        args = dict(min_length=0, max_length=limit, num_beams=self.beam_size, num_return_sequences=1,
                    no_repeat_ngram_size=4)
        with torch.inference_mode():
            # the model code keeps the old tuple-style cache that transformers 5 no longer passes it
            generated = model.generate(**inputs, use_cache=False, **args)
        decoded = tok.decode_batch(generated)
        out = [s.strip() for s in self._ip.postprocess_batch(decoded, lang=tgt_lang)]
        return [_restore_colons(src, dst) for src, dst in zip(sentences, out)]


class FallbackTranslator:
    """Tries the main engine; if it fails (not set up, gated, out of memory) uses the backup engine."""

    def __init__(self, main, backup):
        self.main, self.backup = main, backup
        self._main_broken = False

    @property
    def model_name(self) -> str:
        return self.backup.model_name if self._main_broken else self.main.model_name

    @property
    def is_loaded(self) -> bool:
        return self.backup.is_loaded if self._main_broken else self.main.is_loaded

    def _load(self):
        try:
            if not self._main_broken:
                self.main._load()
                return
        except Exception:  # noqa: BLE001
            logger.exception("IndicTrans2 could not be loaded; using NLLB")
            self._main_broken = True
        self.backup._load()

    def translate(self, text: str, src_lang: str, tgt_lang: str, max_length: int = 400) -> str:
        if not self._main_broken:
            try:
                return self.main.translate(text, src_lang, tgt_lang, max_length)
            except Exception:  # noqa: BLE001
                logger.exception("IndicTrans2 failed; using NLLB from now on")
                self._main_broken = True
        return self.backup.translate(text, src_lang, tgt_lang, max_length)
