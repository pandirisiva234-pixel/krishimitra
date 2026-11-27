import { useEffect, useRef, useState } from "react";
import { getCurrentLocation } from "../utils/location";
import { useSearchParams } from "react-router-dom";
import { AlertCircle, Languages, Mic, Plus, Send, Square, ThumbsDown, ThumbsUp, Volume2 } from "lucide-react";
import { errorMessage } from "../api/client";
import { assistant, conversations } from "../api/endpoints";
import LanguageSelect from "../components/LanguageSelect";
import RelatedVideos from "../components/RelatedVideos";
import SourceList from "../components/SourceList";
import SpeechQueue from "../components/SpeechQueue";
import { Card, EmptyState, PageHeader, Spinner } from "../components/ui";
import { useSpeech } from "../context/SpeechContext";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import useRecorder from "../hooks/useRecorder";
import { splitForSpeech } from "../utils/format";
import { useI18n } from "../i18n";

const EXAMPLES = [
  "టమాటా ఆకులపై మచ్చలు ఉన్నాయి, ఏమి చేయాలి?",
  "धान में यूरिया कब डालें?",
  "Is it a good day to spray pesticide?",
  "ఈరోజు టమాటా ధర ఎంత?",
];

const OPEN_KEY = "krishimitra_open_conversation";
function rememberedConversation() {
  try {
    const v = sessionStorage.getItem(OPEN_KEY);
    return v ? Number(v) : null;
  } catch {
    return null;
  }
}
function rememberConversation(id) {
  try {
    if (id) sessionStorage.setItem(OPEN_KEY, String(id));
    else sessionStorage.removeItem(OPEN_KEY);
  } catch {
    /* storage unavailable: the chat is simply not restored */
  }
}

// Why an answer is not from the verified documents (the backend's fixed English replies tell us)
export function warnLabel(m) {
  const en = m.answer_english || "";
  if (en.startsWith("I am KrishiMitra, a farming assistant")) return "warn.outsideFarming";
  if (en.includes("not from KrishiMitra's verified documents")) return "warn.generalAdvice";
  if (en.includes("could not find information")) return "warn.notInKb";
  if (en.startsWith("Please set your farm location")) return null;
  return "warn.notFromKb";
}

function Message({ m, onFeedback, conversationLanguage }) {
  const { t } = useI18n();
  const [showEnglish, setShowEnglish] = useState(false);
  return (
    <div className="exchange">
      <div className="bubble bubble-user" dir="auto">
        {m.input_mode === "voice" && <Mic size={14} aria-label={t("assistant.spoken")} />} {m.question}
      </div>
      <div className={`bubble bubble-bot ${m.grounded === false ? "bubble-warn" : ""}`}>
        <p className="answer-text" dir="auto">{showEnglish ? m.answer_english : m.answer}</p>
        <div className="answer-meta">
          {m.intent && <span className="tag">{t(`intent.${m.intent}`)}</span>}
          {m.grounded === false && m.intent !== "greeting" && warnLabel(m) && (
            <span className="tag tag-warn">
              <AlertCircle size={12} /> {t(warnLabel(m))}
            </span>
          )}
          {m.answer_english && m.answer_english !== m.answer && (
            <button className="link-btn" onClick={() => setShowEnglish(!showEnglish)}>
              <Languages size={14} /> {showEnglish ? t("common.showMine") : t("common.showEnglish")}
            </button>
          )}
        </div>
        {m.answer && (
          <SpeechQueue
            id={`answer-${m.response_id ?? m.query_id}`}
            chunks={splitForSpeech(m.answer)}
            languageCode={m.language_code || conversationLanguage}
            autoPlay={m.fresh && m.auto_speak}
            label={m.question?.slice(0, 40)}
          />
        )}
        <SourceList sources={m.sources} />
        <RelatedVideos
          question={m.question_english}
          original={m.question}
          languageCode={m.language_code || conversationLanguage}
          intent={m.intent}
          autoLoad={!!m.fresh}
        />
        {m.response_id && (
          <div className="feedback">
            {m.feedback ? (
              <span className="muted small">{t("assistant.thanks")}</span>
            ) : (
              <>
                <span className="muted small">{t("assistant.helpful")}</span>
                <button className="icon-btn" aria-label={t("assistant.yes")} onClick={() => onFeedback(m, true)}>
                  <ThumbsUp size={16} />
                </button>
                <button className="icon-btn" aria-label={t("assistant.no")} onClick={() => onFeedback(m, false)}>
                  <ThumbsDown size={16} />
                </button>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default function VoiceAssistant() {
  const { user } = useAuth();
  const { t, tm, lang: uiLang } = useI18n();
  const toast = useToast();
  const [params, setParams] = useSearchParams();
  const recorder = useRecorder();
  const [language, setLanguage] = useState(uiLang || user?.preferred_language?.code || "en");
  const [speak, setSpeak] = useState(true);
  const [text, setText] = useState("");
  const [audioId, setAudioId] = useState(null);
  const [inputMode, setInputMode] = useState("text");
  const [conversationId, setConversationId] = useState(() =>
    params.get("c") ? Number(params.get("c")) : rememberedConversation(),
  );
  const [conversationLanguage, setConversationLanguage] = useState(null);
  const speech = useSpeech();
  const [messages, setMessages] = useState([]);
  const [stage, setStage] = useState(null); // transcribing | thinking
  const [transcriptInfo, setTranscriptInfo] = useState(null);
  const bottomRef = useRef(null);

  // Continue a conversation: one opened from History (?c=), or the one left open before visiting
  // another page (remembered for this browser tab until "New conversation" is pressed)
  useEffect(() => {
    const id = params.get("c") || (params.get("q") ? null : rememberedConversation());
    if (!id) return;
    conversations
      .get(id)
      .then((c) => {
        setConversationId(c.id);
        setLanguage(c.language_code);
        setConversationLanguage(c.language_code);
        setMessages(c.messages.map((msg) => ({ ...msg, feedback: false })));
      })
      .catch(() => {
        rememberConversation(null); // deleted or not ours: start fresh
        if (params.get("c")) toast.error(t("assistant.cannotOpen"));
      });
  }, [params, toast]);

  useEffect(() => rememberConversation(conversationId), [conversationId]);

  // A new chat answers in the interface language, so changing the app language also changes the answer language
  useEffect(() => {
    if (!conversationId && messages.length === 0) setLanguage(uiLang);
  }, [uiLang]); // eslint-disable-line react-hooks/exhaustive-deps

  // Question sent from another page (e.g. "Ask KrishiMitra about this disease"): ask it once, automatically
  const askedFromLink = useRef(false);
  useEffect(() => {
    const q = params.get("q");
    if (!q || askedFromLink.current) return;
    askedFromLink.current = true;
    setParams({}, { replace: true }); // a page refresh must not ask again
    ask(q);
  }, [params]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    // Braces matter: newer browsers return a Promise from scrollIntoView, which React must not receive
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, stage]);

  // When a recording finishes, send it for transcription
  useEffect(() => {
    if (recorder.state !== "done" || !recorder.result) return;
    const { blob, filename } = recorder.result;
    setStage("transcribing");
    assistant
      .transcribe(blob, filename, language)
      .then((res) => {
        setText(res.text);
        setAudioId(res.audio_id);
        setInputMode("voice");
        setLanguage(res.language_code);
        setTranscriptInfo(res);
      })
      .catch((e) => toast.error(errorMessage(e)))
      .finally(() => {
        setStage(null);
        recorder.reset();
      });
  }, [recorder.state]); // eslint-disable-line react-hooks/exhaustive-deps

  // Where the farmer is right now, for weather questions (falls back to the saved farm location)
  const [here, setHere] = useState(null);
  useEffect(() => {
    getCurrentLocation().then(setHere);
  }, []);

  const ask = async (question = text) => {
    if (!question.trim()) return;
    setStage("thinking");
    try {
      const res = await assistant.ask({
        text: question.trim(),
        language_code: language || null,
        conversation_id: conversationId,
        input_mode: inputMode,
        audio_id: inputMode === "voice" ? audioId : null,
        speak: false, // speech is fetched right after, so the text answer shows sooner
        ...(here ? { latitude: here.lat, longitude: here.lon } : {}),
      });
      setConversationId(res.conversation_id);
      setMessages((prev) => [
        ...prev.map((p) => ({ ...p, fresh: false })),
        {
          ...res, input_mode: inputMode, fresh: true, feedback: false,
          auto_speak: speak, // spoken by the app-wide player, piece by piece
        },
      ]);
      setText("");
      setAudioId(null);
      setInputMode("text");
      setTranscriptInfo(null);
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setStage(null);
    }
  };

  const sendFeedback = async (m, helpful) => {
    try {
      await assistant.feedback({ response_id: m.response_id, is_helpful: helpful });
    } catch (e) {
      if (e.response?.status !== 409) return toast.error(errorMessage(e));
    }
    setMessages((prev) => prev.map((p) => (p.response_id === m.response_id ? { ...p, feedback: true } : p)));
  };

  const newConversation = () => {
    speech.stop(); // a new conversation also stops the voice
    setMessages([]);
    setConversationId(null);
    rememberConversation(null);
    setParams({});
  };

  const recording = recorder.state === "recording";

  return (
    <div className="assistant-page">
      <PageHeader
        title={t("assistant.title")}
        subtitle={t("assistant.subtitle")}
        actions={
          <button className="btn btn-ghost" onClick={newConversation}>
            <Plus size={18} /> {t("assistant.new")}
          </button>
        }
      />

      <Card className="chat-card">
        <div className="chat-log">
          {messages.length === 0 && !stage && (
            <EmptyState icon={Mic} title={t("assistant.firstQuestion")}>
              <p>{t("assistant.tryThese")}</p>
              <div className="chips">
                {EXAMPLES.map((ex) => (
                  <button key={ex} className="chip" onClick={() => setText(ex)}>
                    {ex}
                  </button>
                ))}
              </div>
            </EmptyState>
          )}
          {messages.map((m) => (
            <Message key={m.query_id} m={m} onFeedback={sendFeedback} conversationLanguage={conversationLanguage || language} />
          ))}
          {stage === "thinking" && (
            <div className="bubble bubble-bot">
              <Spinner label={t("assistant.finding")} />
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        <div className="composer">
          <div className="composer-row">
            <div className="field-inline">
              <label htmlFor="lang">{t("assistant.answerIn")}</label>
              <LanguageSelect id="lang" value={language} onChange={setLanguage} />
            </div>
            <label className="toggle">
              <input type="checkbox" checked={speak} onChange={(e) => setSpeak(e.target.checked)} />
              <Volume2 size={16} /> {t("assistant.speak")}
            </label>
          </div>

          {transcriptInfo && (
            <p className="muted small">
              {t("assistant.heardIn", { lang: transcriptInfo.language_code.toUpperCase() })}{" "}
              {transcriptInfo.used_fallback_language
                ? t("assistant.unsureLang")
                : t("assistant.sure", { pct: Math.round(transcriptInfo.language_probability * 100) })}
              . {t("assistant.correct")}
            </p>
          )}

          <div className="composer-input">
            <button
              type="button"
              className={`mic-btn ${recording ? "recording" : ""}`}
              onClick={recording ? recorder.stop : recorder.start}
              disabled={stage !== null}
              aria-label={recording ? t("assistant.stopRec") : t("assistant.startRec")}
              style={{ "--level": recorder.level }}
            >
              {recording ? <Square size={22} /> : <Mic size={24} />}
            </button>
            <textarea
              className="input composer-text"
              rows={2}
              value={recording ? "" : text}
              placeholder={
                recording
                  ? `${t("assistant.listening")} ${recorder.seconds}s / ${recorder.maxSeconds}s`
                  : stage === "transcribing"
                    ? t("assistant.converting")
                    : t("assistant.placeholder")
              }
              onChange={(e) => {
                setText(e.target.value);
                if (!audioId) setInputMode("text");
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  ask();
                }
              }}
              disabled={recording || stage !== null}
            />
            <button className="btn btn-primary" onClick={() => ask()} disabled={!text.trim() || stage !== null}>
              <Send size={18} /> {t("assistant.ask")}
            </button>
          </div>
          {recorder.error && <p className="field-msg">{tm(recorder.error)}</p>}
        </div>
      </Card>
    </div>
  );
}
