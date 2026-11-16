"""Voice assistant pipeline, RAG, conversations and feedback (Modules 2, 3, 8)."""
import subprocess

import httpx
import respx

from tests.conftest import TELUGU_Q, TELUGU_Q_EN, register


def ask(client, headers, **body):
    return client.post("/api/assistant/query", headers=headers, json=body)


def test_telugu_question_full_pipeline(client, farmer, knowledge, services):
    resp = ask(client, farmer["headers"], text=TELUGU_Q)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["language_code"] == "te"  # detected from Telugu script
    assert data["question_english"] == TELUGU_Q_EN  # translated to the pivot language
    assert data["intent"] == "pest_disease"  # keyword fallback (no trained model in tests)
    assert data["grounded"] is True
    assert data["sources"] and data["sources"][0]["title"] == "Tomato and paddy guide"
    assert data["answer"].startswith("<tel_Telu>")  # translated back to Telugu
    assert data["answer_english"] == services.llm.reply
    assert {"language_detect", "translate_in", "intent", "retrieve", "llm", "translate_out", "total"} <= set(data["timings_ms"])
    # The retrieved passage was actually given to Gemini
    assert "mancozeb" in services.llm.prompts[-1]
    assert "district" not in services.llm.prompts[-1] or "Guntur" in services.llm.prompts[-1]


def test_english_question_answered_in_chosen_language(client, farmer, knowledge):
    """The question's language is detected from its script; the answer uses the chosen language."""
    data = ask(client, farmer["headers"], text="How to control early blight on tomato?", language_code="te").json()
    assert data["question_language"] == "en"
    assert data["question_english"] == "How to control early blight on tomato?"  # not run through translation
    assert data["language_code"] == "te"
    assert data["answer"].startswith("<tel_Telu>")


def test_marathi_selected_wins_over_hindi_for_devanagari(client, farmer, knowledge):
    """Hindi and Marathi share one alphabet; the farmer's selected language decides."""
    data = ask(client, farmer["headers"], text="टोमॅटोच्या पानांवर ठिपके आले आहेत", language_code="mr").json()
    assert data["question_language"] == "mr"
    assert data["language_code"] == "mr"
    hindi = ask(client, farmer["headers"], text="टमाटर की पत्तियों पर धब्बे", language_code="en").json()
    assert hindi["question_language"] == "hi"  # no Devanagari language chosen: Hindi is the default


def test_follow_up_goes_into_same_conversation(client, farmer, knowledge):
    first = ask(client, farmer["headers"], text="How to control early blight on tomato?").json()
    second = ask(client, farmer["headers"], text="Which spray for tomato spots?",
                 conversation_id=first["conversation_id"]).json()
    assert second["conversation_id"] == first["conversation_id"]
    convs = client.get("/api/conversations", headers=farmer["headers"]).json()
    assert len(convs) == 1 and convs[0]["message_count"] == 2
    detail = client.get(f"/api/conversations/{first['conversation_id']}", headers=farmer["headers"]).json()
    assert [m["question"] for m in detail["messages"]] == ["How to control early blight on tomato?",
                                                            "Which spray for tomato spots?"]
    assert detail["messages"][0]["intent"] == "pest_disease"


DEFAULT_REPLY = "Remove the spotted lower leaves and spray mancozeb as per the label [1]."


def test_non_farming_question_is_refused(client, farmer, knowledge, services):
    services.llm.reply = "NOT_FARMING"
    try:
        data = ask(client, farmer["headers"], text="What is the price of gold jewellery today?",
                   language_code="en").json()
    finally:
        services.llm.reply = DEFAULT_REPLY
    assert data["grounded"] is False and data["sources"] == []
    assert "farming assistant" in data["answer_english"]


def test_farming_question_outside_documents_gets_labelled_general_advice(client, farmer, knowledge, services):
    services.llm.reply = ["NOT_IN_KNOWLEDGE_BASE", "Mango trees need well-drained soil and regular pruning."]
    try:
        data = ask(client, farmer["headers"], text="tomato leaves spots treatment", language_code="en").json()
    finally:
        services.llm.reply = DEFAULT_REPLY
    assert data["grounded"] is False and data["sources"] == []
    assert data["answer_english"].startswith("Mango trees need")
    assert "not from KrishiMitra's verified documents" in data["answer_english"]


def test_general_advice_can_be_switched_off(client, farmer, knowledge, services, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "GENERAL_FARMING_FALLBACK", False)
    services.llm.reply = "NOT_IN_KNOWLEDGE_BASE"
    try:
        data = ask(client, farmer["headers"], text="tomato leaves spots treatment", language_code="en").json()
    finally:
        services.llm.reply = DEFAULT_REPLY
    assert data["grounded"] is False and "could not find" in data["answer_english"]


def test_greeting_needs_no_ai_call(client, farmer, services):
    before = len(services.llm.prompts)
    data = ask(client, farmer["headers"], text="Hello", language_code="en").json()
    assert data["intent"] == "greeting" and "KrishiMitra" in data["answer"]
    assert len(services.llm.prompts) == before


def test_weather_question_without_location(client, farmer):
    data = ask(client, farmer["headers"], text="Will it rain tomorrow?", language_code="en").json()
    assert data["intent"] == "weather"
    assert "Profile" in data["answer"]


@respx.mock
def test_weather_question_with_location_uses_live_data(client, farmer):
    from tests.test_weather import CURRENT, FORECAST

    respx.get("https://api.openweathermap.org/data/2.5/weather").mock(return_value=httpx.Response(200, json=CURRENT))
    respx.get("https://api.openweathermap.org/data/2.5/forecast").mock(return_value=httpx.Response(200, json=FORECAST))
    client.put("/api/auth/profile", headers=farmer["headers"], json={"latitude": 16.3, "longitude": 80.45})
    data = ask(client, farmer["headers"], text="Is it a good day to spray? Any rain forecast?", language_code="en").json()
    assert data["intent"] == "weather"
    assert data["grounded"] is True
    assert data["sources"][0]["kind"] == "weather"


@respx.mock
def test_weather_uses_current_device_location_first(client, farmer):
    """A farmer who travelled gets weather for where they are now, not the saved farm location."""
    from tests.test_weather import CURRENT, FORECAST

    current = respx.get("https://api.openweathermap.org/data/2.5/weather").mock(
        return_value=httpx.Response(200, json=CURRENT))
    respx.get("https://api.openweathermap.org/data/2.5/forecast").mock(return_value=httpx.Response(200, json=FORECAST))
    client.put("/api/auth/profile", headers=farmer["headers"], json={"latitude": 16.3, "longitude": 80.45})
    data = ask(client, farmer["headers"], text="Will it rain tomorrow?", language_code="en",
               latitude=12.97, longitude=77.59).json()  # now in Bengaluru
    assert data["intent"] == "weather" and data["grounded"] is True
    assert current.calls.last.request.url.params["lat"] == "12.97"


def test_speak_and_audio_download(client, farmer):
    data = ask(client, farmer["headers"], text="Hello", language_code="te", speak=True).json()
    assert data["audio_url"].startswith("/api/assistant/audio/")
    audio = client.get(data["audio_url"], headers=farmer["headers"])
    assert audio.status_code == 200 and audio.headers["content-type"] == "audio/mpeg"
    spoken = client.post("/api/assistant/speak", headers=farmer["headers"],
                         json={"text": "Spray in the evening.", "language_code": "hi", "translate_from_english": True})
    assert spoken.status_code == 200
    assert spoken.json()["text"].startswith("<hin_Deva>")


def test_audio_path_traversal_blocked(client, farmer):
    resp = client.get("/api/assistant/audio/..%2F..%2F.env", headers=farmer["headers"])
    assert resp.status_code == 404


def test_feedback_once_per_answer(client, farmer, knowledge):
    data = ask(client, farmer["headers"], text="tomato leaf spots", language_code="en").json()
    body = {"response_id": data["response_id"], "is_helpful": True, "comment": "useful"}
    assert client.post("/api/feedback", headers=farmer["headers"], json=body).status_code == 201
    assert client.post("/api/feedback", headers=farmer["headers"], json=body).status_code == 409


def test_users_cannot_see_each_others_conversations(client, farmer):
    data = ask(client, farmer["headers"], text="Hello", language_code="en").json()
    other = register(client, phone="9123456780")
    headers = {"Authorization": f"Bearer {other['access_token']}"}
    assert client.get(f"/api/conversations/{data['conversation_id']}", headers=headers).status_code == 404
    assert client.post("/api/feedback", headers=headers,
                       json={"response_id": data["response_id"], "is_helpful": False}).status_code == 404
    assert ask(client, headers, text="Hi", conversation_id=data["conversation_id"]).status_code == 404


def test_delete_conversation(client, farmer):
    data = ask(client, farmer["headers"], text="Hello", language_code="en").json()
    assert client.delete(f"/api/conversations/{data['conversation_id']}", headers=farmer["headers"]).status_code == 200
    assert client.get("/api/conversations", headers=farmer["headers"]).json() == []


def _wav(path, seconds):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}",
                    "-c:a", "libopus", str(path)], check=True)
    return path.read_bytes()


def test_transcribe_real_audio_conversion(client, farmer, services, tmp_path):
    audio = _wav(tmp_path / "q.webm", 2)
    resp = client.post("/api/voice/transcribe", headers=farmer["headers"],
                       files={"audio": ("question.webm", audio, "audio/webm")})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["text"] == TELUGU_Q and data["language_code"] == "te"
    assert data["used_fallback_language"] is False
    assert 1.8 < data["duration_sec"] < 2.3  # measured by ffprobe on the converted WAV
    # The recording is linked to the question that follows
    ans = ask(client, farmer["headers"], text=data["text"], input_mode="voice", audio_id=data["audio_id"]).json()
    detail = client.get(f"/api/conversations/{ans['conversation_id']}", headers=farmer["headers"]).json()
    assert detail["messages"][0]["input_mode"] == "voice"


def test_transcribe_low_confidence_uses_profile_language(client, farmer, services, tmp_path):
    services.stt.prob, services.stt.calls = 0.3, []
    try:
        data = client.post("/api/voice/transcribe", headers=farmer["headers"],
                           files={"audio": ("q.webm", _wav(tmp_path / "q.webm", 2), "audio/webm")}).json()
    finally:
        services.stt.prob = 0.95
    assert data["used_fallback_language"] is True
    assert data["language_code"] == "te"  # farmer's preferred language
    assert services.stt.calls == [None, "te"]  # second pass forced to Telugu


def test_transcribe_rejects_bad_files(client, farmer, tmp_path):
    fake = client.post("/api/voice/transcribe", headers=farmer["headers"],
                       files={"audio": ("evil.webm", b"MZ\x90\x00 not audio", "audio/webm")})
    assert fake.status_code == 400 and fake.json()["error"]["code"] == "invalid_file"
    short = client.post("/api/voice/transcribe", headers=farmer["headers"],
                        files={"audio": ("s.webm", _wav(tmp_path / "s.webm", 0.2), "audio/webm")})
    assert short.status_code == 400 and "too short" in short.json()["error"]["message"]
    exe = client.post("/api/voice/transcribe", headers=farmer["headers"],
                      files={"audio": ("x.exe", b"MZ", "application/octet-stream")})
    assert exe.status_code == 400


def test_transcribe_low_confidence_uses_selected_language(client, farmer, services, tmp_path):
    """An unsure Whisper result falls back to the language chosen on screen, not the profile language."""
    services.stt.prob, services.stt.calls = 0.3, []
    try:
        data = client.post("/api/voice/transcribe", headers=farmer["headers"], data={"language_hint": "hi"},
                           files={"audio": ("q.webm", _wav(tmp_path / "q.webm", 2), "audio/webm")}).json()
    finally:
        services.stt.prob = 0.95
    assert data["language_code"] == "hi" and data["used_fallback_language"] is True
    assert services.stt.calls == [None, "hi"]


def test_question_with_farm_terms_is_never_refused(client, farmer, knowledge, services):
    services.llm.reply = "NOT_FARMING"
    try:
        data = ask(client, farmer["headers"], text="ప్రస్తుతం ఊరియా రేట్ ఎలా ఉంది", language_code="te").json()
    finally:
        services.llm.reply = DEFAULT_REPLY
    assert "farming assistant" not in data["answer_english"]
    assert "could not find" in data["answer_english"]


def test_gemini_refines_non_english_question_before_search(client, farmer, knowledge, services, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "QUERY_REFINE_WITH_LLM", True)
    services.llm.reply = ["How to control early blight spots on tomato leaves?", DEFAULT_REPLY]
    try:
        before = len(services.llm.prompts)
        data = ask(client, farmer["headers"], text="టమాటా ఆకులపై మచ్చలు", language_code="te").json()
    finally:
        services.llm.reply = DEFAULT_REPLY
    refine_prompt = services.llm.prompts[before]
    assert "FARMER QUESTION (Telugu): టమాటా ఆకులపై మచ్చలు" in refine_prompt
    assert data["question_english"] == "How to control early blight spots on tomato leaves?"
    assert data["grounded"] is True


def test_english_question_is_not_refined(client, farmer, knowledge, services, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "QUERY_REFINE_WITH_LLM", True)
    before = len(services.llm.prompts)
    ask(client, farmer["headers"], text="tomato leaves spots treatment", language_code="en")
    assert len(services.llm.prompts) == before + 1  # only the answer, no refinement call


def test_translate_endpoint_keeps_lines(client, farmer):
    r = client.post("/api/assistant/translate", headers=farmer["headers"],
                    json={"text": "Remove leaves.\nSpray as per label.", "language_code": "te"})
    assert r.status_code == 200, r.text
    assert r.json()["text"].count("\n") == 1 and r.json()["language_code"] == "te"
    r = client.post("/api/assistant/translate", headers=farmer["headers"], json={"text": "Hello", "language_code": "en"})
    assert r.json()["text"] == "Hello"


def test_beta_language_answer_is_translated_by_gemini(client, farmer, knowledge, services, monkeypatch):
    """Urdu answers go through Gemini (NLLB turned 'blight' into a bird name there)."""
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "LLM_TRANSLATE_LANGUAGES", ["ur"])
    services.llm.reply = [DEFAULT_REPLY, "متاثرہ نچلے پتے ہٹا دیں اور لیبل کے مطابق مینکوزیب چھڑکیں [1]۔"]
    try:
        before = len(services.llm.prompts)
        data = ask(client, farmer["headers"], text="How to control early blight on tomato?", language_code="ur").json()
    finally:
        services.llm.reply = DEFAULT_REPLY
    assert len(services.llm.prompts) == before + 2  # the answer, then its translation
    assert services.llm.prompts[-1] == data["answer_english"]
    assert data["answer"].startswith("متاثرہ")
    assert "<urd_Arab>" not in data["answer"]  # the NLLB fake was not used


def test_gemini_translation_falls_back_to_nllb(client, farmer, knowledge, services, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "LLM_TRANSLATE_LANGUAGES", ["ur"])
    services.llm.reply = [DEFAULT_REPLY, "Sorry, I can only reply in English."]  # not a translation
    try:
        data = ask(client, farmer["headers"], text="How to control early blight on tomato?", language_code="ur").json()
    finally:
        services.llm.reply = DEFAULT_REPLY
    assert data["answer"].startswith("<urd_Arab>")  # NLLB backup


def test_tested_languages_still_use_nllb(client, farmer, knowledge, services, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "LLM_TRANSLATE_LANGUAGES", ["ur"])
    before = len(services.llm.prompts)
    data = ask(client, farmer["headers"], text="How to control early blight on tomato?", language_code="te").json()
    assert len(services.llm.prompts) == before + 1
    assert data["answer"].startswith("<tel_Telu>")


def test_gemini_translation_retried_when_another_alphabet_slips_in(client, farmer, knowledge, services, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "LLM_TRANSLATE_LANGUAGES", ["kn"])
    services.llm.reply = [DEFAULT_REPLY, "ಕತ್ತริ ಹುಳುಗಳನ್ನು ನಾಶ ಮಾಡಿ [1].", "ಕತ್ತರಿ ಹುಳುಗಳನ್ನು ನಾಶ ಮಾಡಿ [1]."]
    try:
        data = ask(client, farmer["headers"], text="How to control early blight on tomato?", language_code="kn").json()
    finally:
        services.llm.reply = DEFAULT_REPLY
    assert data["answer"].startswith("ಕತ್ತರಿ")
