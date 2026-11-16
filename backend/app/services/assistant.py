"""The voice/text assistant pipeline (orchestrator).

    question (any language)
      -> language detection -> NLLB to English -> intent classification
      -> weather route (OpenWeather + advisories)   or   RAG route (ChromaDB + FlashRank)
      -> Gemini answer (grounded, cited) -> NLLB back to the farmer's language
      -> Edge-TTS audio (optional) -> saved to PostgreSQL

CPU-heavy model calls run in a thread pool so the server stays responsive.
"""
import asyncio
import logging
import unicodedata
import re
import uuid
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.core.config import Settings
from app.core.exceptions import AppError, FileValidationError, NotFoundError, ServiceNotConfiguredError
from app.models import ConversationHistory, Intent, Language, Query, Response, User
from app.schemas.assistant import AskRequest
from app.services.container import ServiceContainer
from app.services.language_service import get_language, get_language_by_whisper_code, script_map
from app.services.translation.languages import DEFAULT_LANGUAGES
from app.services.llm.prompts import (
    FALLBACK_NOT_FOUND,
    GENERAL_ADVICE_NOTE,
    GENERAL_FARMING_SYSTEM_PROMPT,
    GREETING_REPLY,
    NOT_FARMING_MARKER,
    NOT_FARMING_REPLY,
    NOT_FOUND_MARKER,
    SYSTEM_PROMPT,
    QUERY_REFINE_SYSTEM_PROMPT,
    WEATHER_SYSTEM_PROMPT,
    build_general_prompt,
    build_query_refine_prompt,
    build_translate_system_prompt,
    strip_greeting,
    clean_refined_query,
    build_rag_prompt,
    build_weather_prompt,
    clean_markdown,
)
from app.services.speech.audio_utils import audio_duration_seconds, convert_to_wav16k
from app.services.translation.language_detect import detect_language
from app.services.weather.advisories import weather_summary_text
from app.services.translation.post_edit import post_edit
from app.services.nlp.glossary import expand_query, glossary_terms
from app.utils.timing import StageTimer

logger = logging.getLogger(__name__)

ENGLISH_NLLB = "eng_Latn"
_LANG_BY_NLLB = {row["nllb_code"]: row for row in DEFAULT_LANGUAGES}
AUDIO_ID_RE = re.compile(r"^[a-f0-9]{32}$")
# an English letter glued to an Indian-script letter inside one word, e.g. "ತೆಗೆAಗಿ" (a translation slip)
_MIXED_WORD = re.compile(r"[\u0900-\u0DFF\u0600-\u06FF][A-Za-z]|[A-Za-z][\u0900-\u0DFF\u0600-\u06FF]")


def _foreign_letters(text: str, script: str) -> list[str]:
    """Letters (and vowel signs) that belong neither to the language's own alphabet nor to English."""
    from app.services.translation.languages import SCRIPT_RANGES

    allowed = SCRIPT_RANGES.get(script, []) + SCRIPT_RANGES["Latin"] + [(0x0964, 0x0965)]  # + danda marks
    out = []
    for c in text:
        if ord(c) < 0x80 or not (c.isalpha() or unicodedata.category(c) in ("Mn", "Mc")):
            continue  # ASCII, digits, punctuation, spaces
        if 0x0300 <= ord(c) <= 0x036F or 0x200B <= ord(c) <= 0x200D:
            continue  # combining accents and zero-width joiners used inside Indic words
        if not any(lo <= ord(c) <= hi for lo, hi in allowed):
            out.append(c)
    return out


def audio_url(path: str | None) -> str | None:
    return f"/api/assistant/audio/{Path(path).name}" if path else None


class AssistantService:
    def __init__(self, services: ServiceContainer, settings: Settings):
        self.s = services
        self.settings = settings

    # ------------------------------------------------------------------ helpers
    async def translate(self, text: str, src: str, tgt: str) -> str:
        if src == tgt:
            return text
        if src == ENGLISH_NLLB and text.strip():
            gemini_text = await self._translate_with_llm(text, tgt)
            if gemini_text:
                return gemini_text
        try:
            return await run_in_threadpool(self.s.translator.translate, text, src, tgt)
        except AppError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.exception("Translation failed")
            raise ServiceNotConfiguredError(
                "Translation model is not available. Check internet access for the first download, "
                "or the NLLB settings in .env."
            ) from exc

    async def _translate_with_llm(self, text: str, tgt: str) -> str | None:
        """Gemini translation for languages where NLLB loses farm words. None = use NLLB instead."""
        lang = _LANG_BY_NLLB.get(tgt)
        if not lang or lang["code"] not in self.settings.LLM_TRANSLATE_LANGUAGES or not self.s.llm.is_configured:
            return None
        try:
            for _attempt in range(2):
                out = clean_markdown(await asyncio.wait_for(self.s.llm.generate(
                    text, build_translate_system_prompt(lang["name"]), retries=1, max_output_tokens=2048),
                    timeout=self.settings.LLM_TRANSLATE_TIMEOUT_S))
                # a reply still mostly in English is not a translation
                latin = sum(1 for c in out if "a" <= c.lower() <= "z")
                letters = sum(1 for c in out if c.isalpha()) or 1
                if latin / letters >= 0.4:
                    return None
                if not _foreign_letters(out, lang["script"]) and not _MIXED_WORD.search(out):
                    return out
                # letters from another alphabet slipped in (e.g. Thai inside Kannada): ask once more
                logger.warning("Gemini translation to %s had letters from another script; retrying", lang["code"])
            return out if len(_foreign_letters(out, lang["script"])) <= 2 else None
        except Exception:  # noqa: BLE001  - never fail the answer because of this: NLLB is the backup
            logger.warning("Gemini translation to %s failed; using NLLB", lang["code"], exc_info=True)
            return None

    def _farmer_context(self, user: User) -> str | None:
        parts = []
        if user.district or user.state:
            parts.append(f"located in {', '.join(p for p in (user.district, user.state) if p)}")
        if user.primary_crops:
            parts.append(f"grows {user.primary_crops}")
        return "; ".join(parts) or None

    # ------------------------------------------------------------- transcription
    async def transcribe(self, db: Session, user: User, data: bytes, ext: str,
                         language_hint: str | None = None) -> dict:
        """language_hint: the language selected on screen; used when Whisper is unsure (else the profile language)."""
        timer = StageTimer()
        audio_id = uuid.uuid4().hex
        audio_dir = self.settings.audio_upload_dir
        audio_dir.mkdir(parents=True, exist_ok=True)
        raw_path = audio_dir / f"{audio_id}{ext}"
        wav_path = audio_dir / f"{audio_id}.wav"
        raw_path.write_bytes(data)
        try:
            with timer.stage("convert"):
                await run_in_threadpool(convert_to_wav16k, raw_path, wav_path)
                duration = await run_in_threadpool(audio_duration_seconds, wav_path)
        finally:
            raw_path.unlink(missing_ok=True)  # keep only the normalised WAV
        if duration > self.settings.MAX_AUDIO_SECONDS:
            wav_path.unlink(missing_ok=True)
            raise FileValidationError(f"Recording is too long. Maximum is {self.settings.MAX_AUDIO_SECONDS} seconds")
        if duration < 0.5:
            wav_path.unlink(missing_ok=True)
            raise FileValidationError("Recording is too short. Please hold the button and speak")

        try:
            with timer.stage("stt"):
                hint_lang = get_language(db, language_hint) if language_hint else None
                result = await run_in_threadpool(
                    self.s.stt.transcribe, wav_path, None, hint_lang.whisper_code if hint_lang else None
                )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Speech recognition failed")
            raise ServiceNotConfiguredError(
                "Speech recognition model is not available. Check internet access for the first download."
            ) from exc

        detected = get_language_by_whisper_code(db, result.language)
        used_fallback = bool(getattr(result, "hinted", False))  # the on-screen choice was used
        if detected is None or result.language_probability < self.settings.WHISPER_MIN_LANGUAGE_PROB:
            # Whisper is unsure or heard an unsupported language: trust the farmer's profile language
            used_fallback = True
            detected = get_language(db, language_hint) if language_hint else user.preferred_language
            with timer.stage("stt_retry"):
                result_forced = await run_in_threadpool(self.s.stt.transcribe, wav_path, detected.whisper_code)
            text = result_forced.text
        else:
            text = result.text

        if not text.strip():
            raise FileValidationError("No speech was detected. Please speak closer to the microphone")
        return {
            "text": text,
            "language_code": detected.code,
            "detected_language": result.language,
            "language_probability": round(result.language_probability, 3),
            "used_fallback_language": used_fallback,
            "duration_sec": round(duration, 2),
            "processing_ms": timer.total_ms(),
            "audio_id": audio_id,
        }

    # ------------------------------------------------------------------ question
    async def ask(self, db: Session, user: User, req: AskRequest) -> dict:
        timer = StageTimer()
        text = req.text.strip()

        # 1. Languages. The QUESTION language is detected from the text itself (script),
        #    falling back to the chosen/preferred language. The ANSWER language is the one the
        #    farmer chose (req.language_code), else the question's language. So a farmer can
        #    type in English and still hear the answer in Telugu.
        with timer.stage("language_detect"):
            chosen = get_language(db, req.language_code) if req.language_code else None
            det = detect_language(text, script_map(db))
            if det.language_code and det.confidence >= 0.5:
                in_lang, lang_conf = get_language(db, det.language_code), det.confidence
                if chosen and chosen.script == det.script and chosen.code != in_lang.code:
                    in_lang = chosen  # same alphabet (e.g. Marathi vs Hindi): trust the farmer's choice
            else:
                in_lang, lang_conf = chosen or user.preferred_language, None
            lang = chosen or in_lang  # answer language

        # 2. Translate to English (the pivot language)
        with timer.stage("translate_in"):
            english = await self.translate(text, in_lang.nllb_code, ENGLISH_NLLB)
        # Add the correct English farm terms NLLB may have missed (e.g. thrips, not "lotus worm")
        farm_terms = glossary_terms(text, in_lang.code)
        english = expand_query(english, text, in_lang.code)
        if in_lang.code != "en" and self.settings.QUERY_REFINE_WITH_LLM and self.s.llm.is_configured:
            # Gemini reads the farmer's own words and fixes NLLB's farm terms before the search
            with timer.stage("refine_query"):
                try:
                    refined = await asyncio.wait_for(self.s.llm.generate(
                        build_query_refine_prompt(text, in_lang.name, english, farm_terms),
                        QUERY_REFINE_SYSTEM_PROMPT, retries=1,
                    ), timeout=self.settings.LLM_REFINE_TIMEOUT_S)
                    english = clean_refined_query(refined, english)
                except Exception:  # noqa: BLE001  - never fail the answer because of this optional step
                    logger.warning("Query refinement failed; using the NLLB translation", exc_info=True)
        logger.info("Question (%s) in English: %s", in_lang.code, english)

        # 3. Intent
        with timer.stage("intent"):
            intent = await run_in_threadpool(self.s.intent.predict, english)

        # 4-5. Route and generate
        sources: list[dict] = []
        grounded = False
        model_name = None
        if intent.intent == "greeting":
            answer_en = GREETING_REPLY
        elif intent.intent == "weather":
            answer_en, sources, grounded, model_name = await self._answer_weather(
                db, user, english, timer, req.latitude, req.longitude)
        else:
            answer_en, sources, grounded, model_name = await self._answer_rag(
                user, english, timer, original=(text, in_lang.name, farm_terms)
            )
        answer_en = clean_markdown(answer_en)
        if intent.intent != "greeting":
            answer_en = strip_greeting(answer_en)

        # 6. Back to the farmer's language
        with timer.stage("translate_out"):
            answer_local = await self.translate(answer_en, ENGLISH_NLLB, lang.nllb_code)
            answer_local = post_edit(answer_local, answer_en, lang.code)

        # 7. Speech
        tts_path = None
        if req.speak:
            with timer.stage("tts"):
                tts_path = str(await self.s.tts.synthesize(answer_local, lang.tts_voice, gtts_lang=lang.code))

        # 8. Save
        with timer.stage("save"):
            saved = self._save(db, user, req, in_lang, lang, lang_conf, english, intent, answer_en, answer_local,
                               grounded, sources, model_name, tts_path, timer)
        return saved

    async def _answer_rag(self, user: User, english: str, timer: StageTimer, original=None):
        with timer.stage("retrieve"):
            try:
                chunks = await run_in_threadpool(self.s.retriever.retrieve, english)
            except Exception as exc:  # noqa: BLE001
                logger.exception("Retrieval failed")
                raise ServiceNotConfiguredError(
                    "Knowledge search is not available. Check that the embedding model can be downloaded."
                ) from exc
        if not chunks:
            return await self._answer_general(english, timer, original)

        passages = []
        sources = []
        for i, c in enumerate(chunks, start=1):
            label = f"{c.title}, p. {c.page}" if c.page else c.title
            passages.append((i, label, c.text))
            sources.append({"index": i, "title": c.title, "page": c.page, "document_id": c.document_id,
                            "score": round(c.score, 4), "snippet": c.text[:300], "kind": "document"})

        with timer.stage("llm"):
            answer = await self.s.llm.generate(
                build_rag_prompt(english, passages, self._farmer_context(user)), SYSTEM_PROMPT
            )
        if NOT_FOUND_MARKER in answer:
            return await self._answer_general(english, timer, original)
        # Keep only sources Gemini actually cited, so the list matches the answer
        cited = {int(n) for n in re.findall(r"\[(\d+)\]", answer)}
        if cited:
            sources = [s for s in sources if s["index"] in cited]
        return answer, sources, True, self.s.llm.model

    async def _answer_general(self, english: str, timer: StageTimer, original=None):
        """No verified passage: general farming advice, clearly labelled (grounded=False), or a refusal.

        `original` = (question in the farmer's words, language name, glossary farm terms found).
        Gemini reads the original too, so a bad translation cannot hide a farming question.
        """
        if not self.settings.GENERAL_FARMING_FALLBACK or not self.s.llm.is_configured:
            return FALLBACK_NOT_FOUND, [], False, None
        text, lang_name, farm_terms = original or (None, None, [])
        with timer.stage("llm_general"):
            answer = await self.s.llm.generate(
                build_general_prompt(english, text, lang_name, farm_terms), GENERAL_FARMING_SYSTEM_PROMPT
            )
        if NOT_FARMING_MARKER in answer:
            # a question with known farm words is never refused; the honest "not found" reply is used instead
            return (FALLBACK_NOT_FOUND if farm_terms else NOT_FARMING_REPLY), [], False, self.s.llm.model
        return f"{answer.strip()}\n\n{GENERAL_ADVICE_NOTE}", [], False, self.s.llm.model

    async def _answer_weather(self, db: Session, user: User, english: str, timer: StageTimer,
                              lat: float | None = None, lon: float | None = None):
        # Where the farmer is now (sent by the browser) comes first; the saved farm location is the backup
        if lat is None or lon is None:
            lat, lon = user.latitude, user.longitude
        if lat is None or lon is None:
            return ("Please allow location access in your browser, or set your farm location on the Profile page, "
                    "so I can give weather advice for your area.", [], False, None)
        with timer.stage("weather"):
            forecast = await self.s.weather.forecast(db, lat, lon, user.id)
            current = await self.s.weather.current(db, lat, lon, user.id)
        summary = weather_summary_text(current, forecast["daily"], forecast["advisories"])
        source = [{"index": 1, "title": "OpenWeather live forecast", "page": None, "document_id": None,
                   "score": None, "snippet": summary[:300], "kind": "weather"}]
        if not self.s.llm.is_configured:
            return summary, source, True, None  # rule-based answer still works without Gemini
        with timer.stage("llm"):
            answer = await self.s.llm.generate(build_weather_prompt(english, summary), WEATHER_SYSTEM_PROMPT)
        return answer, source, True, self.s.llm.model

    def _save(self, db, user, req, in_lang: Language, lang: Language, lang_conf, english, intent, answer_en,
              answer_local, grounded, sources, model_name, tts_path, timer: StageTimer) -> dict:
        """in_lang = language the question was asked in (stored on the query, used for statistics);
        lang = language of the answer (stored on the conversation)."""
        if req.conversation_id:
            conv = db.get(ConversationHistory, req.conversation_id)
            if not conv or conv.user_id != user.id:
                raise NotFoundError("Conversation not found")
        else:
            conv = ConversationHistory(user_id=user.id, language_id=lang.id, title=req.text.strip()[:80])
            db.add(conv)
            db.flush()

        audio_path, audio_duration = None, None
        if req.audio_id and AUDIO_ID_RE.match(req.audio_id):
            candidate = self.settings.audio_upload_dir / f"{req.audio_id}.wav"
            if candidate.exists():
                audio_path = str(candidate)
                try:
                    audio_duration = round(audio_duration_seconds(candidate), 2)
                except AppError:
                    audio_duration = None

        intent_row = db.scalars(select(Intent).where(Intent.name == intent.intent)).first()
        query = Query(
            conversation_id=conv.id, user_id=user.id, language_id=in_lang.id,
            intent_id=intent_row.id if intent_row else None, input_mode=req.input_mode,
            original_text=req.text.strip(), english_text=english, detected_language=in_lang.code,
            language_confidence=lang_conf, intent_confidence=intent.confidence,
            audio_path=audio_path, audio_duration_sec=audio_duration,
        )
        db.add(query)
        db.flush()
        timings = timer.as_dict()
        logger.info("Answer timings (ms): %s", timings)
        response = Response(
            query_id=query.id, answer_english=answer_en, answer_text=answer_local, grounded=grounded,
            sources=sources, model_name=model_name, audio_path=tts_path, timings_ms=timings,
            total_ms=timings["total"],
        )
        db.add(response)
        conv.updated_at = func.now()
        db.commit()
        return {
            "conversation_id": conv.id,
            "query_id": query.id,
            "response_id": response.id,
            "question": query.original_text,
            "question_english": english,
            "question_language": in_lang.code,
            "language_code": lang.code,
            "intent": intent.intent,
            "intent_confidence": intent.confidence,
            "answer": answer_local,
            "answer_english": answer_en,
            "grounded": grounded,
            "sources": sources,
            "audio_url": audio_url(tts_path),
            "timings_ms": timings,
        }
