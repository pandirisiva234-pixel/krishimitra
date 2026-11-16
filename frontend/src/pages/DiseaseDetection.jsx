import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AlertTriangle, Camera, CheckCircle2, ImagePlus, Leaf, MessageSquare, Plus, ScanLine, Sparkles } from "lucide-react";
import { errorMessage } from "../api/client";
import { disease } from "../api/endpoints";
import CameraCapture from "../components/CameraCapture";
import ListenLanguage, { useTranslatedText } from "../components/ListenLanguage";
import SpeechQueue from "../components/SpeechQueue";
import { AuthImage, Card, ConfidenceBar, EmptyState, PageHeader, Spinner } from "../components/ui";
import { useAuth } from "../context/AuthContext";
import { useSpeech } from "../context/SpeechContext";
import { useToast } from "../context/ToastContext";
import { formatDateTime, pct, prettyLabel, splitForSpeech } from "../utils/format";

const MAX_MB = 5;
const SPEECH_PREFIX = "opinion-";

/** "How to control early blight in tomato? What are the symptoms and how to prevent it?" */
export function diseaseQuestion(d) {
  const crop = String(d.crop || "").replace(/_/g, " ").replace(/\s*\(.*\)\s*/g, " ").trim().toLowerCase();
  const name = String(d.disease_name || "").replace(/_/g, " ").trim().toLowerCase();
  return `How to control ${name} in ${crop}? What are the symptoms and how to prevent it?`;
}

/** Gemini looks at the same photo when the trained model is unsure; clearly labelled as general advice. */
function SecondOpinion({ predictionId, languageCode, listenLanguage }) {
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const [op, setOp] = useState(null);
  const [english, setEnglish] = useState(false);
  const get = async () => {
    setBusy(true);
    try {
      setOp(await disease.secondOpinion(predictionId, languageCode));
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };
  if (!op) {
    return (
      <div className="ask-more">
        <div>
          <strong>Still want an answer?</strong>
          <p className="muted small">An AI can look at the same photo and suggest likely causes. It is a general opinion, not a diagnosis.</p>
        </div>
        <button className="btn btn-gold" onClick={get} disabled={busy}>
          {busy ? <Spinner label="Looking at the photo…" size={16} /> : (<><Sparkles size={18} /> Get AI second opinion</>)}
        </button>
      </div>
    );
  }
  return <OpinionView op={op} predictionId={predictionId} listenLanguage={listenLanguage} english={english} setEnglish={setEnglish} />;
}

function OpinionView({ op, predictionId, listenLanguage, english, setEnglish }) {
  const lang = listenLanguage || op.language_code;
  const translated = useTranslatedText(op.summary_english, lang, { [op.language_code]: op.summary });
  const showEnglish = english || lang === "en";
  const text = showEnglish ? op.summary_english : translated.text || op.summary_english;
  return (
    <div className="second-opinion">
      <div className="card-head">
        <h2>
          <Sparkles size={18} /> AI second opinion
        </h2>
        <span className="tag tag-warn">General advice · confidence {op.confidence}</span>
      </div>
      {translated.loading && !showEnglish ? <Spinner label="Translating…" size={16} /> : <p className="answer-text">{text}</p>}
      <div className="row">
        {!translated.loading && (
          <SpeechQueue
            id={`opinion-${predictionId}-${showEnglish ? "en" : lang}`}
            chunks={splitForSpeech(text)}
            languageCode={showEnglish ? "en" : lang}
            label="AI second opinion"
          />
        )}
        {lang !== "en" && (
          <button className="link-btn" onClick={() => setEnglish(!english)}>
            {english ? "Show in my language" : "Show in English"}
          </button>
        )}
      </div>
    </div>
  );
}

const SAFETY_EN =
  "Follow the product label for any chemical, wear gloves and a mask, and check with your local agriculture officer before treating a large area.";
const SECTIONS = [
  ["About", "description"],
  ["Symptoms to confirm", "symptoms"],
  ["What to do now", "treatment"],
  ["Prevention", "prevention"],
];

/** Disease advice as lines: heading, text, heading, text, ..., safety. Translated as one block (lines are kept). */
export function adviceLines(d) {
  const lines = [];
  for (const [heading, key] of SECTIONS) {
    if (d[key]) lines.push(heading, String(d[key]).replace(/\s*\n\s*/g, " "));
  }
  lines.push(SAFETY_EN);
  return lines;
}

function Result({ result, languageCode, onLanguage }) {
  const navigate = useNavigate();
  const [english, setEnglish] = useState(false);
  const d = result.disease;
  // Follow-up question for the voice assistant, answered from the official documents with sources
  const followUp = d && !d.is_healthy ? diseaseQuestion(d) : null;
  const englishLines = d ? adviceLines(d) : [];
  const englishText = englishLines.join("\n");
  const translated = useTranslatedText(d && !result.is_uncertain ? englishText : "", languageCode);
  const showEnglish = english || languageCode === "en";
  const lines = showEnglish || !translated.text ? englishLines : translated.text.split("\n");
  const safety = lines[lines.length - 1];
  const pairs = [];
  for (let i = 0; i < lines.length - 2; i += 2) pairs.push([lines[i], lines[i + 1]]); // last line is the safety note
  const spoken = `${d ? `${d.crop}, ${d.disease_name}.` : ""}\n${lines.join("\n")}`;

  return (
    <div className="result">
      <div className={`result-head ${result.is_uncertain ? "uncertain" : d?.is_healthy ? "healthy" : "diseased"}`}>
        {result.is_uncertain ? <AlertTriangle size={22} /> : d?.is_healthy ? <CheckCircle2 size={22} /> : <Leaf size={22} />}
        <div>
          <div className="result-title">
            {result.is_uncertain
              ? `Not sure (best guess: ${d ? `${d.crop} · ${d.disease_name}` : prettyLabel(result.predicted_label)})`
              : d
                ? `${d.crop} · ${d.disease_name}`
                : prettyLabel(result.predicted_label)}
          </div>
          <div className="small">{result.message}</div>
        </div>
      </div>
      <div className="result-confidence">
        <span className="muted small">Model confidence</span>
        <ConfidenceBar value={result.confidence} />
      </div>

      {d && !result.is_uncertain && (
        <div className="disease-info">
          <div className="row lang-row">
            <ListenLanguage value={languageCode} onChange={onLanguage} />
            {languageCode !== "en" && (
              <button className="link-btn" onClick={() => setEnglish(!english)}>
                {english ? "Show in my language" : "Show in English"}
              </button>
            )}
          </div>
          {translated.loading && !showEnglish ? (
            <Spinner label="Translating…" size={16} />
          ) : (
            <>
              {pairs.map(([heading, text], i) => (
                <section key={i}>
                  <h3>{heading}</h3>
                  <p>{text}</p>
                </section>
              ))}
              <p className="muted small">{safety}</p>
              {translated.failed && !showEnglish && <p className="muted small">Translation is not available right now; showing English.</p>}
              <SpeechQueue
                id={`disease-${result.id}-${showEnglish ? "en" : languageCode}`}
                chunks={splitForSpeech(spoken)}
                languageCode={showEnglish ? "en" : languageCode}
                label={d ? `${d.crop} · ${d.disease_name}` : "Disease advice"}
              />
            </>
          )}
          {followUp && (
            <div className="ask-more">
              <div>
                <strong>Need more detail?</strong>
                <p className="muted small">
                  Get crop-specific advice from the official guides (NIPHM, ICAR), with sources, in your language.
                </p>
              </div>
              <button className="btn btn-gold" onClick={() => navigate(`/assistant?q=${encodeURIComponent(followUp)}`)}>
                <MessageSquare size={18} /> Ask KrishiMitra about this disease
              </button>
            </div>
          )}
        </div>
      )}

      {result.is_uncertain && (
        <>
          <div className="row">
            <ListenLanguage value={languageCode} onChange={onLanguage} id="opinion-lang" />
          </div>
          <SecondOpinion predictionId={result.id} languageCode={languageCode} listenLanguage={languageCode} />
        </>
      )}

      <details className="top-k">
        <summary>Other possibilities</summary>
        <ul>
          {result.top_predictions.map((p) => (
            <li key={p.label}>
              <span>{p.disease_name ? `${p.crop} · ${p.disease_name}` : prettyLabel(p.label)}</span>
              <span>{pct(p.confidence, 1)}</span>
            </li>
          ))}
        </ul>
        <p className="muted small">
          Model {result.model_version || "—"} · {result.inference_ms} ms · sharpness {result.blur_score}
        </p>
      </details>
    </div>
  );
}

export default function DiseaseDetection() {
  const { user } = useAuth();
  const toast = useToast();
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [camera, setCamera] = useState(false);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [history, setHistory] = useState([]);
  const inputRef = useRef(null);
  const speech = useSpeech();
  const [listenLanguage, setListenLanguage] = useState(user.preferred_language?.code || "en");

  // Clear the photo and result (and stop this page's voice) to start a fresh scan
  const newScan = () => {
    if (String(speech.id || "").startsWith(SPEECH_PREFIX)) speech.stop();
    setFile(null);
    setPreview(null);
    setResult(null);
    setCamera(false);
    setBusy(false);
  };

  const loadHistory = useCallback(() => disease.history(12).then(setHistory).catch(() => {}), []);
  useEffect(() => {
    loadHistory();
  }, [loadHistory]);
  useEffect(() => () => preview && URL.revokeObjectURL(preview), [preview]);

  const choose = (blob, name) => {
    if (!blob.type.startsWith("image/")) return toast.error("Please choose a photo (JPG or PNG).");
    if (blob.size > MAX_MB * 1024 * 1024) return toast.error(`Photo is larger than ${MAX_MB} MB.`);
    setFile({ blob, name });
    setPreview(URL.createObjectURL(blob));
    setResult(null);
    setCamera(false);
  };

  const analyse = async () => {
    setBusy(true);
    try {
      const res = await disease.predict(file.blob, file.name);
      setResult(res);
      loadHistory();
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <PageHeader
        title="Plant disease detection"
        subtitle="Photograph one affected leaf in daylight. The model suggests the likely disease."
        actions={
          <button className="btn btn-ghost" onClick={newScan} disabled={!file && !result}>
            <Plus size={18} /> New scan
          </button>
        }
      />
      <div className="grid-2">
        <Card title="Leaf photo" icon={ImagePlus}>
          {camera ? (
            <CameraCapture onCapture={(blob) => choose(blob, "camera.jpg")} onClose={() => setCamera(false)} />
          ) : (
            <>
              <div
                className={`dropzone ${preview ? "has-image" : ""}`}
                onClick={() => inputRef.current?.click()}
                onDragOver={(e) => e.preventDefault()}
                onDrop={(e) => {
                  e.preventDefault();
                  const f = e.dataTransfer.files?.[0];
                  if (f) choose(f, f.name);
                }}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => e.key === "Enter" && inputRef.current?.click()}
              >
                {preview ? (
                  <img src={preview} alt="Selected leaf" />
                ) : (
                  <div className="dropzone-empty">
                    <ImagePlus size={36} />
                    <p>Tap to choose a photo, or drop it here</p>
                    <p className="muted small">JPG or PNG, up to {MAX_MB} MB</p>
                  </div>
                )}
              </div>
              <input
                ref={inputRef}
                type="file"
                accept="image/jpeg,image/png,image/webp"
                capture="environment"
                hidden
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) choose(f, f.name);
                  e.target.value = "";
                }}
              />
              <div className="row">
                <button className="btn btn-ghost" onClick={() => setCamera(true)}>
                  <Camera size={18} /> Use camera
                </button>
                <button className="btn btn-primary" onClick={analyse} disabled={!file || busy}>
                  {busy ? <Spinner label="Analysing…" size={16} /> : (<><ScanLine size={18} /> Detect disease</>)}
                </button>
              </div>
            </>
          )}
        </Card>

        <Card title="Result" icon={Leaf}>
          {result ? (
            <Result result={result} languageCode={listenLanguage} onLanguage={setListenLanguage} />
          ) : (
            <EmptyState icon={ScanLine} title="No result yet">
              Choose or capture a photo, then tap “Detect disease”.
            </EmptyState>
          )}
        </Card>
      </div>

      <Card title="Previous scans" className="mt">
        {history.length ? (
          <div className="scan-grid">
            {history.map((h) => (
              <button key={h.id} className="scan" onClick={() => setResult(h)}>
                <AuthImage url={h.image_url} alt={h.predicted_label} className="scan-img" />
                <span className="scan-label">{h.disease ? `${h.disease.crop} · ${h.disease.disease_name}` : prettyLabel(h.predicted_label)}</span>
                <span className="muted small">
                  {h.is_uncertain ? "uncertain" : pct(h.confidence)} · {formatDateTime(h.created_at)}
                </span>
              </button>
            ))}
          </div>
        ) : (
          <p className="muted">Your scans will appear here.</p>
        )}
      </Card>
    </div>
  );
}
