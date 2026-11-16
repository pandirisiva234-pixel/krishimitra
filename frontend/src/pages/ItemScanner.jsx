// Farm item scanner: photo of a pesticide bottle, fertilizer bag, seed packet or tool ->
// what it is, what it is used for and how to use it safely, in the farmer's language.
import { useEffect, useRef, useState } from "react";
import { AlertTriangle, Camera, FlaskConical, ImagePlus, Languages, PackageSearch, Plus, ScanLine, ShieldAlert } from "lucide-react";
import { errorMessage } from "../api/client";
import { items } from "../api/endpoints";
import CameraCapture from "../components/CameraCapture";
import ListenLanguage, { useTranslatedText } from "../components/ListenLanguage";
import SpeechQueue from "../components/SpeechQueue";
import { Card, EmptyState, PageHeader, Spinner } from "../components/ui";
import { useAuth } from "../context/AuthContext";
import { useSpeech } from "../context/SpeechContext";
import { useToast } from "../context/ToastContext";
import { splitForSpeech } from "../utils/format";

const MAX_MB = 5;
const SPEECH_PREFIX = "item-";
const TOX_CLASS = { red: "tox-red", yellow: "tox-yellow", blue: "tox-blue", green: "tox-green" };

function ItemResult({ item, listenLanguage, onLanguage }) {
  const [english, setEnglish] = useState(false);
  const lang = listenLanguage || item.language_code;
  const translated = useTranslatedText(item.summary_english, lang, { [item.language_code]: item.summary });
  const showEnglish = english || lang === "en";
  const text = showEnglish ? item.summary_english : translated.text || item.summary_english;
  if (!item.is_farm_item) {
    return (
      <div className="result-head uncertain">
        <AlertTriangle size={22} />
        <div>
          <div className="result-title">Not a farm product</div>
          <div className="small">{text}</div>
        </div>
      </div>
    );
  }
  const rows = [
    ["Active ingredient", item.active_ingredient],
    ["Used for", item.used_for],
    ["Meant for", item.targets],
    ["How to use", item.how_to_use],
    ["Safety", item.safety],
  ].filter(([, v]) => v);
  return (
    <div className="item-result">
      <div className="result-head diseased">
        <FlaskConical size={22} />
        <div>
          <div className="result-title">{item.product_name || "Farm item"}</div>
          <div className="small">
            <span className="tag capitalize">{item.category}</span>{" "}
            {item.toxicity_colour && (
              <span className={`tag tox ${TOX_CLASS[item.toxicity_colour]}`}>
                ◆ {item.toxicity_colour} label · {item.toxicity_meaning}
              </span>
            )}{" "}
            <span className="muted">Confidence: {item.confidence}</span>
          </div>
        </div>
      </div>
      {!item.label_readable && (
        <p className="banner banner-error small">The label was hard to read. Take a closer, sharper photo of the label.</p>
      )}
      <table className="table compact mt">
        <tbody>
          {rows.map(([k, v]) => (
            <tr key={k}>
              <th>{k}</th>
              <td>{v}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="item-local">
        <div className="card-head">
          <ListenLanguage value={listenLanguage} onChange={onLanguage} id="item-lang" />
          {lang !== "en" && (
            <button className="link-btn" onClick={() => setEnglish(!english)}>
              {english ? "Show in my language" : "Show in English"}
            </button>
          )}
        </div>
        {translated.loading && !showEnglish ? (
          <Spinner label="Translating…" size={16} />
        ) : (
          <>
            <p className="answer-text">{text}</p>
            <SpeechQueue
              id={`item-${item.product_name || "unknown"}-${item.summary.length}-${showEnglish ? "en" : lang}`}
              chunks={splitForSpeech(text)}
              languageCode={showEnglish ? "en" : lang}
              label={item.product_name || "Farm item"}
            />
          </>
        )}
      </div>
      <p className="muted small">
        <ShieldAlert size={14} /> Information is read from the photo by AI and may be wrong. Always follow the dose
        printed on the label, and check with your agriculture officer or veterinary doctor before use.
      </p>
    </div>
  );
}

export default function ItemScanner() {
  const { user } = useAuth();
  const toast = useToast();
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [camera, setCamera] = useState(false);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
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
  useEffect(() => () => preview && URL.revokeObjectURL(preview), [preview]);

  const choose = (blob, name) => {
    if (!blob.type.startsWith("image/")) return toast.error("Please choose a photo (JPG or PNG).");
    if (blob.size > MAX_MB * 1024 * 1024) return toast.error(`Photo is larger than ${MAX_MB} MB.`);
    setFile({ blob, name });
    setPreview(URL.createObjectURL(blob));
    setResult(null);
    setCamera(false);
  };

  const identify = async () => {
    setBusy(true);
    try {
      setResult(await items.identify(file.blob, file.name, listenLanguage));
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <PageHeader
        title="Farm item scanner"
        subtitle="Photograph a pesticide bottle, fertilizer bag, seed packet, animal medicine or tool. Keep the label visible."
        actions={
          <button className="btn btn-ghost" onClick={newScan} disabled={!file && !result}>
            <Plus size={18} /> New scan
          </button>
        }
      />
      <div className="grid-2">
        <Card title="Item photo" icon={ImagePlus}>
          {camera ? (
            <CameraCapture onCapture={(blob) => choose(blob, "camera.jpg")} onClose={() => setCamera(false)} />
          ) : (
            <>
              <div
                className="dropzone"
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
                  <img src={preview} alt="Selected item" />
                ) : (
                  <div className="dropzone-empty">
                    <PackageSearch size={36} />
                    <p>Tap to choose a photo of the item, or drop it here</p>
                    <p className="muted small">Label facing the camera · JPG or PNG, up to {MAX_MB} MB</p>
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
                <button className="btn btn-primary" onClick={identify} disabled={!file || busy}>
                  {busy ? <Spinner label="Reading the label…" size={16} /> : (<><ScanLine size={18} /> Identify item</>)}
                </button>
              </div>
            </>
          )}
        </Card>
        <Card title="What is this?" icon={FlaskConical}>
          {result ? (
            <ItemResult item={result} listenLanguage={listenLanguage} onLanguage={setListenLanguage} />
          ) : (
            <EmptyState icon={PackageSearch} title="No item scanned yet">
              Choose a photo, then tap “Identify item”.
            </EmptyState>
          )}
        </Card>
      </div>
    </div>
  );
}
