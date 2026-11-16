"""Unit tests for pure functions (no web server, no database)."""
import pytest

from app.core.security import hash_password, verify_password
from app.services.nlp.intent_classifier import keyword_intent
from app.services.rag.ingest import chunk_pages, clean_text
from app.services.translation.language_detect import detect_language
from app.services.translation.nllb_translator import split_sentences
from app.utils.files import _looks_like

SCRIPTS = {"Telugu": "te", "Devanagari": "hi", "Tamil": "ta", "Kannada": "kn", "Malayalam": "ml",
           "Bengali": "bn", "Gujarati": "gu", "Arabic": "ur", "Latin": "en"}


@pytest.mark.parametrize("text,code", [
    ("వరి పంటకు ఎరువు ఎప్పుడు వేయాలి?", "te"),
    ("गेहूं में कौन सी खाद डालें?", "hi"),
    ("நெல் பயிருக்கு எப்போது தண்ணீர் விட வேண்டும்?", "ta"),
    ("ಟೊಮೆಟೊ ಎಲೆಗಳ ಮೇಲೆ ಕಲೆಗಳು", "kn"),
    ("When should I sow groundnut?", "en"),
    ("നെല്ലിന് എപ്പോൾ വളം ഇടണം?", "ml"),
    ("ধানে কখন সার দিতে হবে?", "bn"),
    ("કપાસમાં કયું ખાતર નાખવું?", "gu"),
    ("گندم میں کون سی کھاد ڈالیں؟", "ur"),
])
def test_script_language_detection(text, code):
    result = detect_language(text, SCRIPTS)
    assert result.language_code == code
    assert result.confidence > 0.9


def test_mixed_and_empty_text():
    mixed = detect_language("DAP ఎరువు ఎంత వేయాలి", SCRIPTS)
    assert mixed.language_code == "te"  # majority script wins
    assert detect_language("123 ?!", SCRIPTS).language_code is None
    assert detect_language("pantaku neeru", SCRIPTS).language_code == "en"  # documented limitation


def test_sentence_split():
    assert split_sentences("First. Second! Third?\nFourth। Fifth") == ["First.", "Second!", "Third?", "Fourth।", "Fifth"]


def test_clean_and_chunk():
    raw = "Nitro-\ngen is needed.\nKeep soil moist.\n\n12\n\nApply   urea in two splits."
    cleaned = clean_text(raw)
    assert "Nitrogen" in cleaned and "  " not in cleaned and "\n12\n" not in cleaned
    chunks = chunk_pages([(3, "word " * 400)], chunk_size=300, overlap=50)
    assert len(chunks) > 1 and all(c.page == 3 for c in chunks)
    assert all(len(c.text) <= 300 for c in chunks)


@pytest.mark.parametrize("text,intent", [
    ("How much urea should I apply to paddy?", "fertilizer_soil"),
    ("White flies on my chilli plants", "pest_disease"),
    ("Will it rain tomorrow?", "weather"),
    ("When to harvest groundnut and how to store it?", "harvest_storage"),
    ("How often should I irrigate cotton with drip?", "irrigation_water"),
    ("Thank you", "greeting"),
    ("Tell me a joke about cricket", "other"),
])
def test_keyword_intent_fallback(text, intent):
    assert keyword_intent(text).intent == intent


def test_password_hashing():
    h = hash_password("Secret123")
    assert h != "Secret123" and verify_password("Secret123", h)
    assert not verify_password("secret123", h)
    assert not verify_password("x", "not-a-hash")


def test_magic_bytes():
    assert _looks_like("image", b"\xff\xd8\xff\xe0" + b"0" * 12)
    assert _looks_like("image", b"\x89PNG\r\n\x1a\n" + b"0" * 8)
    assert not _looks_like("image", b"%PDF-1.7" + b"0" * 8)
    assert _looks_like("audio", b"\x1a\x45\xdf\xa3" + b"0" * 12)
    assert _looks_like("audio", b"RIFF\x00\x00\x00\x00WAVEfmt ")
    assert _looks_like("document", b"%PDF-1.7")
    assert not _looks_like("audio", b"MZ\x90\x00" + b"0" * 12)


def test_fix_script_maps_devanagari_to_telugu():
    from app.services.speech.whisper_stt import fix_script

    assert fix_script("टमाटा", "te") == "టమాటా"
    assert fix_script("धान में यूरिया", "hi") == "धान में यूरिया"  # Hindi stays Devanagari
    assert fix_script("టమాటా ఆకులపై", "te") == "టమాటా ఆకులపై"  # already correct script
    assert fix_script("thrips in chilli", "te") == "thrips in chilli"


def test_fix_script_maps_kannada_letters_to_telugu():
    from app.services.speech.whisper_stt import fix_script

    assert fix_script("ತಮಾಟಾ", "te") == "తమాటా"
    assert fix_script("ತಮಾಟಾ", "kn") == "ತಮಾಟಾ"  # Kannada speech keeps Kannada script


def test_language_model_used_only_when_folder_exists(tmp_path):
    from app.services.speech.whisper_stt import SpeechToText

    stt = SpeechToText("medium", "cpu", "int8", tmp_path, language_models={"te": tmp_path / "missing"})
    assert stt._language_model("te") is None  # folder missing -> general model
    assert stt._language_model("hi") is None  # no fine-tuned model configured
    assert stt._language_model(None) is None


def test_translate_batches_all_lines_and_keeps_line_breaks(tmp_path):
    from app.services.translation.nllb_translator import Translator

    tr = Translator("m", "transformers", tmp_path)
    calls = []

    def fake(sentences, src, tgt, max_length):
        calls.append(list(sentences))
        return [s.upper() for s in sentences]

    tr._translate_sentences = fake
    out = tr.translate("1. Remove leaves. Burn them.\n\n2. Spray mancozeb.", "eng_Latn", "tel_Telu")
    assert out == "1. REMOVE LEAVES. BURN THEM.\n\n2. SPRAY MANCOZEB."
    assert len(calls) == 1  # one batch for the whole answer


def test_translator_auto_backend_falls_back_without_ct2_folder(tmp_path):
    from app.services.translation.nllb_translator import Translator

    assert Translator("m", "auto", tmp_path, str(tmp_path / "missing")).backend == "transformers"
    (tmp_path / "ct2").mkdir()
    (tmp_path / "ct2" / "model.bin").write_bytes(b"x")
    assert Translator("m", "auto", tmp_path, str(tmp_path / "ct2")).backend == "ctranslate2"


def test_glossary_adds_correct_farm_terms():
    from app.services.nlp.glossary import expand_query, glossary_terms

    assert expand_query("How to prevent lotus worms in pepper?", "మిరపలో తామర పురుగుల నివారణ ఎలా", "te") == (
        "How to prevent lotus worms in pepper? (thrips, chilli)"
    )
    assert glossary_terms("వరిలో అగ్గి తెగులు", "te") == ["blast disease", "paddy rice"]  # not also "disease"
    assert glossary_terms("ఫిబ్రవరిలో", "te") == []  # "వరి" inside another word is ignored
    assert expand_query("Thrips in chilli", "మిరపలో తామర పురుగు", "te") == "Thrips in chilli"  # nothing missing
    assert expand_query("When to apply urea to paddy?", "धान में यूरिया कब डालें?", "hi") == (
        "When to apply urea to paddy? (paddy rice)"
    )


def test_glossary_tolerates_one_misheard_letter_in_long_terms():
    from app.services.nlp.glossary import glossary_terms

    assert glossary_terms("మెరుపలో తామల పురుగుల నివారణ ఎలా", "te") == ["thrips"]  # తామల ≈ తామర
    assert glossary_terms("ఈ రోజు వర్షం పడుతుందా", "te") == ["today", "rain"]
    assert glossary_terms("నాకు సహాయం చేయండి", "te") == []  # no farm words, nothing added


def test_spray_timing_questions_go_to_weather():
    from app.services.nlp.glossary import expand_query
    from app.services.nlp.intent_classifier import keyword_intent

    assert keyword_intent("Is it a good day to spray pesticide?").intent == "weather"
    assert keyword_intent("Can I apply urea tomorrow?").intent == "weather"
    assert keyword_intent("Which pesticide for whitefly in cotton?").intent == "pest_disease"
    # "విచికారి" is a misheard "పిచికారి" (spray); the glossary still finds it
    q = expand_query("Can I do the vichikari of the worm medicine today?", "ఈ రోజు పురుగు మందు విచికారి చేయవచ్చు", "te")
    assert "spray" in q and keyword_intent(q).intent == "weather"


def test_clean_markdown_removes_stars_and_hashes():
    from app.services.llm.prompts import clean_markdown

    out = clean_markdown("**Advice:**\n* Wind: 16 km/h\n## Note\nWind is *too strong* to spray.")
    assert out == "Advice:\n- Wind: 16 km/h\nNote\nWind is too strong to spray."


def test_glossary_matches_split_and_joined_words():
    from app.services.nlp.glossary import glossary_terms

    assert glossary_terms("వేరు శనగకు ఏ ఎరువులు వేయాలి", "te") == ["groundnut", "fertilizer"]
    assert glossary_terms("ప్రస్తుతం ఊరియా రేట్ ఎలా ఉంది", "te") == ["urea"]
    assert glossary_terms("ಟೊಮೇಟೊ ಎಲೆಗಳ ಮೇಲೆ ಕಲೆಗಳಿವೆ", "kn") == ["tomato"]


def test_post_edit_fixes_known_farm_mistranslations_only_with_trigger():
    from app.services.translation.post_edit import post_edit

    assert post_edit("బియ్యంలో మగ మొసళ్ళకు", "Traps for male moths in rice", "te") == "వరిలో మగ రెక్కల పురుగులకు"
    assert post_edit("పశువులను కాపాడండి", "Protect natural enemies", "te") == "మిత్ర పురుగులను కాపాడండి"
    assert post_edit("పశువులకు నీరు", "Give water to the cattle", "te") == "పశువులకు నీరు"  # no trigger
    assert post_edit("बियाणे", "rice", "hi") == "बियाणे"  # rules are per language
    assert post_edit("మట్టి గింజల కోసం", "For groundnut, apply gypsum", "te") == "వేరుశనగ కోసం"


def test_translation_drops_repeated_sentence(tmp_path):
    from app.services.translation.nllb_translator import Translator

    tr = Translator("m", "transformers", tmp_path)
    tr._translate_sentences = lambda s, a, b, c: ["నీరు ఇవ్వండి.", "నీరు ఇవ్వండి.", "వైద్యుని సంప్రదించండి."]
    assert tr.translate("Give water. Give clean water. Call a vet.", "eng_Latn", "tel_Telu") == (
        "నీరు ఇవ్వండి. వైద్యుని సంప్రదించండి."
    )


def test_general_prompt_includes_original_question_and_terms():
    from app.services.llm.prompts import build_general_prompt

    p = build_general_prompt("What is the village rate now?", "ప్రస్తుతం ఊరియా రేట్ ఎలా ఉంది", "Telugu", ["urea"])
    assert "ORIGINAL QUESTION (Telugu)" in p and "urea" in p


def test_selected_language_wins_between_similar_indian_languages(tmp_path):
    import wave
    from types import SimpleNamespace

    import numpy as np

    from app.services.speech.whisper_stt import SpeechToText

    wav = tmp_path / "a.wav"
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
        w.writeframes((np.zeros(16000)).astype(np.int16).tobytes())

    class FakeModel:
        def __init__(self):
            self.used = None

        def detect_language(self, audio, vad_filter=False):
            return "te", 0.88, [("te", 0.88), ("kn", 0.09), ("en", 0.02)]

        def transcribe(self, audio, language=None, **kw):
            self.used = language
            return iter([SimpleNamespace(text="text")]), SimpleNamespace(duration=1.0, language=language)

    stt = SpeechToText("medium", "cpu", "int8", tmp_path)
    model = FakeModel()
    stt._load = lambda: model
    r = stt.transcribe(wav, hint="kn")
    assert (r.language, r.hinted, model.used) == ("kn", True, "kn")
    r = stt.transcribe(wav, hint="en")  # English is not a look-alike of Telugu: keep Whisper's choice
    assert (r.language, r.hinted) == ("te", False)


def test_clean_refined_query_rejects_bad_output():
    from app.services.llm.prompts import clean_refined_query

    assert clean_refined_query('"How to control thrips in chilli?"\nExtra line', "x") == "How to control thrips in chilli?"
    assert clean_refined_query("", "fallback") == "fallback"
    assert clean_refined_query("NOT_FARMING", "fallback") == "fallback"
    assert clean_refined_query("a" * 400, "fallback") == "fallback"


def test_post_edit_fixes_broken_app_letter_in_marathi():
    from app.services.translation.post_edit import post_edit
    assert post_edit("अॅपच्या पानावर", "on the app's page", "mr") == "ॲपच्या पानावर"


def test_post_edit_fixes_blight_in_urdu():
    from app.services.translation.post_edit import post_edit
    assert post_edit("ابتدائی بلبل", "early blight", "ur") == "ابتدائی جھلسا"


def test_indictrans_keeps_lines_and_pivots_through_english():
    from app.services.translation.indictrans_translator import IndicTransTranslator

    t = IndicTransTranslator(cache_dir=None)
    calls = []

    def fake(sentences, src, tgt):
        calls.append((src, tgt))
        return [f"<{tgt}>{s}" for s in sentences]

    t._translate_sentences = fake
    out = t.translate("Remove leaves. Spray.\n2. Wait", "eng_Latn", "tel_Telu")
    assert out == "<tel_Telu>Remove leaves. <tel_Telu>Spray.\n<tel_Telu>2. Wait"
    t.translate("x", "tel_Telu", "kan_Knda")  # Indian -> Indian goes through English
    assert calls[-2:] == [("tel_Telu", "eng_Latn"), ("eng_Latn", "kan_Knda")]


def test_indictrans_processor_matches_ai4bharat_toolkit():
    """IndicTrans2 reads every Brahmic script in Devanagari letters; outputs go back to the farmer's script.
    Expected strings were produced by AI4Bharat's own IndicTransToolkit."""
    from app.services.translation.indictrans_translator import IndicNLPProcessor

    ip = IndicNLPProcessor()
    assert ip.preprocess_batch(["వరి పంటకు యూరియా ఎప్పుడు వేయాలి?"], "tel_Telu", "eng_Latn") == [
        "tel_Telu eng_Latn वरि पंटकु यूरिया ऎप्पुडु वेयालि ?"]
    assert ip.preprocess_batch(["Spray mancozeb [1]."], "eng_Latn", "kan_Knda") == [
        "eng_Latn kan_Knda Spray mancozeb [ 1 ] ."]
    assert ip.postprocess_batch(["भत्तक्कॆ यूरिया हाकि ।"], "kan_Knda") == ["ಭತ್ತಕ್ಕೆ ಯೂರಿಯಾ ಹಾಕಿ."]
    assert ip.postprocess_batch(["धान में खाद डालें ।"], "hin_Deva") == ["धान में खाद डालें।"]
    assert ip.postprocess_batch(["This is a test ."], "eng_Latn") == ["This is a test."]
    # Urdu is not transliterated (its own alphabet), and needs no extra package
    assert ip.preprocess_batch(["کھاد کب ڈالیں؟"], "urd_Arab", "eng_Latn")[0].startswith("urd_Arab eng_Latn کھاد")


def test_fallback_translator_switches_to_nllb_when_indictrans_fails():
    from app.services.translation.indictrans_translator import FallbackTranslator

    class Broken:
        model_name, is_loaded = "IndicTrans2", False

        def translate(self, *a):
            raise OSError("401 gated repo")

        def _load(self):
            raise OSError("401 gated repo")

    class Nllb:
        model_name, is_loaded = "nllb", True

        def translate(self, text, src, tgt, max_length=400):
            return f"<{tgt}>{text}"

        def _load(self):
            pass

    f = FallbackTranslator(Broken(), Nllb())
    assert f.translate("Hi", "eng_Latn", "tel_Telu") == "<tel_Telu>Hi"
    assert f.model_name == "nllb"  # stays on the backup afterwards


def test_strip_greeting_keeps_the_real_answer():
    from app.services.llm.prompts import strip_greeting

    assert strip_greeting("Hello, I am KrishiMitra. This is a common pest problem in maize.") == \
        "This is a common pest problem in maize."
    assert strip_greeting("Hello.") == "Hello."  # nothing else left: keep as is
    assert strip_greeting("Remove the leaves.") == "Remove the leaves."


def test_post_edit_fixes_maize_in_kannada():
    from app.services.translation.post_edit import post_edit

    assert post_edit("ಮಧುಮೇಹದಲ್ಲಿನ ಕೀಟ", "a pest problem in maize", "kn") == "ಮೆಕ್ಕೆಜೋಳದಲ್ಲಿನ ಕೀಟ"


def test_post_edit_neem_in_kannada():
    from app.services.translation.post_edit import post_edit

    assert post_edit("ನಿಮ್ ಎಣ್ಣೆಯನ್ನು ಸಿಂಪಡಿಸಿ", "spray neem oil", "kn") == "ಬೇವಿನ ಎಣ್ಣೆಯನ್ನು ಸಿಂಪಡಿಸಿ"


def test_pest_answers_have_problem_cure_prevention_layout():
    from app.services.llm.prompts import GENERAL_FARMING_SYSTEM_PROMPT, SYSTEM_PROMPT

    for prompt in (SYSTEM_PROMPT, GENERAL_FARMING_SYSTEM_PROMPT):
        assert "Problem:" in prompt and "Cure:" in prompt and "Prevention:" in prompt


def test_foreign_letters_finds_thai_inside_kannada():
    from app.services.assistant import _foreign_letters

    assert _foreign_letters("ಕತ್ತริ ಹುಳುಗಳು", "Kannada") == ["ร", "ิ"]
    assert _foreign_letters("ಕತ್ತರಿ ಹುಳುಗಳು (KVK) 1800-180-1551।", "Kannada") == []
    assert _foreign_letters("میرے ٹماٹر کے پودوں، ۔", "Arabic") == []
    assert _foreign_letters("ధాన్యం — “క్రిమి” …", "Telugu") == []


def test_trained_intent_model_saying_other_is_corrected_by_keywords(tmp_path):
    import joblib
    from sklearn.dummy import DummyClassifier

    from app.services.nlp.intent_classifier import IntentClassifier

    model = DummyClassifier(strategy="constant", constant="other").fit(["a", "b"], ["other", "weather"])
    joblib.dump({"method": "tfidf", "pipeline": model, "labels": ["other", "weather"]}, tmp_path / "m.joblib")
    clf = IntentClassifier(tmp_path / "m.joblib")
    assert clf.predict("Worms have come on the maize leaves, what to do?").intent == "pest_disease"
    assert clf.predict("Tell me something").intent == "other"


def test_indictrans_tokenizer_reads_vocab_files(tmp_path):
    """input = [src tag, tgt tag] + SentencePiece pieces + </s>; output pieces are joined back to text."""
    import json

    import sentencepiece as spm

    from app.services.translation.indictrans_translator import IndicTransTokenizer

    (tmp_path / "c.txt").write_text("\n".join(["Spray neem oil on the leaves.", "धान में खाद डालें"] * 40))
    spm.SentencePieceTrainer.train(input=str(tmp_path / "c.txt"), model_prefix=str(tmp_path / "m"), vocab_size=40,
                                   character_coverage=1.0, hard_vocab_limit=False, minloglevel=2)
    sp = spm.SentencePieceProcessor(model_file=str(tmp_path / "m.model"))
    vocab = {"<s>": 0, "<pad>": 1, "</s>": 2, "<unk>": 3, "eng_Latn": 4, "tel_Telu": 5}
    for i in range(sp.get_piece_size()):
        vocab.setdefault(sp.id_to_piece(i), len(vocab))
    for name in ("dict.SRC.json", "dict.TGT.json"):
        (tmp_path / name).write_text(json.dumps(vocab, ensure_ascii=False), encoding="utf-8")
    files = {"dict.SRC.json": tmp_path / "dict.SRC.json", "dict.TGT.json": tmp_path / "dict.TGT.json",
             "model.SRC": str(tmp_path / "m.model"), "model.TGT": str(tmp_path / "m.model")}
    tok = IndicTransTokenizer(files)
    enc = tok.encode_batch(["eng_Latn tel_Telu Spray neem oil", "eng_Latn tel_Telu Spray"])
    ids = enc["input_ids"].tolist()
    assert ids[0][:2] == [4, 5] and ids[0][-1] == 2  # language tags first, </s> last
    assert ids[1][-1] == 1 and enc["attention_mask"].tolist()[1][-1] == 0  # padded and masked
    seq = [2] + [vocab[p] for p in sp.encode("धान में खाद", out_type=str)] + [2, 1]
    assert tok.decode_batch([seq]) == ["धान में खाद"]


def test_compat_shims_can_run_twice():
    """Both IndicTrans2 models call this; the second call must not fail on the first call's stand-in."""
    from app.services.translation.indictrans_translator import _install_compat_shims

    _install_compat_shims()
    _install_compat_shims()
    from transformers.onnx import OnnxConfig, OnnxSeq2SeqConfigWithPast  # what AI4Bharat's config file does

    assert issubclass(OnnxSeq2SeqConfigWithPast, OnnxConfig)


def test_glossary_jowar_and_maize_find_the_fall_armyworm_documents():
    from app.services.nlp.glossary import glossary_terms

    assert "maize" in " ".join(glossary_terms("ಜೋಳದ ಎಲೆಯ ಮೇಲೆ ಹುಳುಗಳು", "kn"))
    assert glossary_terms("ಮೆಕ್ಕೆಜೋಳದ ಎಲೆ", "kn") == ["maize corn"]  # not also read as jowar
    assert "fall armyworm" in glossary_terms("మొక్కజొన్నలో కత్తెర పురుగు", "te")


def test_crops_in_question():
    from app.services.rag.retriever import crops_in

    assert crops_in("Worms have come on the leaves of jowar (sorghum jowar maize)") == ["maize"]
    assert crops_in("Brown spots on tomato and chillies") == ["tomato", "chilli"]
    assert crops_in("When will it rain?") == []


def test_retriever_ranks_the_named_crop_documents_first():
    from app.services.rag.retriever import Retriever

    class Emb:
        def encode(self, texts):
            return [[0.0] for _ in texts]

    class Store:
        def query(self, vec, k):
            return [
                {"id": "g", "text": "cutworm in groundnut", "distance": 0.2,
                 "metadata": {"title": "NIPHM IPM Package Groundnut", "page": 3, "document_id": 1}},
                {"id": "m", "text": "fall armyworm in maize", "distance": 0.3,
                 "metadata": {"title": "NIPHM IPM Package Maize", "page": 9, "document_id": 2}},
            ]

    class Rerank:
        def rerank(self, query, passages):
            scores = {"g": 0.6, "m": 0.5}  # groundnut scores higher on its own...
            return sorted(({"meta": p["meta"], "score": scores[p["id"]]} for p in passages),
                          key=lambda r: r["score"], reverse=True)

    chunks = Retriever(Emb(), Store(), Rerank(), top_k=5, top_n=2).retrieve("worms on jowar leaves")
    assert chunks[0].title == "NIPHM IPM Package Maize"  # ...but the farmer asked about jowar/maize


def test_mixed_word_detection():
    from app.services.assistant import _MIXED_WORD

    assert _MIXED_WORD.search("ತೆಗೆAಗಿ")
    assert not _MIXED_WORD.search("ಕೃಷಿ ವಿಜ್ಞಾನ ಕೇಂದ್ರ (KVK) mancozeb")


def test_indictrans_colon_written_as_visarga_is_restored():
    from app.services.translation.indictrans_translator import _restore_colons

    assert _restore_colons("Problem: stem borers damage the shoots.", "ಸಮಸ್ಯೆಃ ಕಾಂಡ ಕೊರಕ") == "ಸಮಸ್ಯೆ: ಕಾಂಡ ಕೊರಕ"
    assert _restore_colons("Cure:", "ಚಿಕಿತ್ಸೆಃ") == "ಚಿಕಿತ್ಸೆ:"
    assert _restore_colons("No colon here.", "ಪುನಃ ಮಾಡಿ") == "ಪುನಃ ಮಾಡಿ"  # a real visarga stays
