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
import { useI18n } from "../i18n";

const MAX_MB = 5;
const SPEECH_PREFIX = "item-";
const TOX_CLASS = { red: "tox-red", yellow: "tox-yellow", blue: "tox-blue", green: "tox-green" };

function ItemResult({ item, listenLanguage, onLanguage }) {
  const { t } = useI18n();
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
          <div className="result-title">{t("items.notFarm")}</div>
          <div className="small">{text}</div>
        </div>
      </div>
    );
  }
  const rows = [
    [t("items.ingredient"), item.active_ingredient],
    [t("items.usedFor"), item.used_for],
    [t("items.meantFor"), item.targets],
    [t("items.howTo"), item.how_to_use],
    [t("items.safety"), item.safety],
  ].filter(([, v]) => v);
  return (
    <div className="item-result">
      <div className="result-head diseased">
        <FlaskConical size={22} />
        <div>
          <div className="result-title">{item.product_name || t("items.farmItem")}</div>
          <div className="small">
            <span className="tag capitalize">{item.category}</span>{" "}
            {item.toxicity_colour && (
              <span className={`tag tox ${TOX_CLASS[item.toxicity_colour]}`}>
                ◆ {item.toxicity_colour} {t("items.label")} · {item.toxicity_meaning}
              </span>
            )}{" "}
            <span className="muted">{t("disease.confidence")}: {item.confidence}</span>
          </div>
        </div>
      </div>
      {!item.label_readable && (
        <p className="banner banner-error small">{t("items.hardToRead")}</p>
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
              {english ? t("common.showMine") : t("common.showEnglish")}
            </button>
          )}
        </div>
        {translated.loading && !showEnglish ? (
          <Spinner label={t("common.translating")} size={16} />
        ) : (
          <>
            <p className="answer-text">{text}</p>
            <SpeechQueue
              id={`item-${item.product_name || "unknown"}-${item.summary.length}-${showEnglish ? "en" : lang}`}
              chunks={splitForSpeech(text)}
              languageCode={showEnglish ? "en" : lang}
              label={item.product_name || t("items.farmItem")}
            />
          </>
        )}
      </div>
      <p className="muted small">
        <ShieldAlert size={14} /> {t("items.disclaimer")}
      </p>
    </div>
  );
}

export default function ItemScanner() {
  const { user } = useAuth();
  const { t, lang } = useI18n();
  const toast = useToast();
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [camera, setCamera] = useState(false);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const inputRef = useRef(null);
  const speech = useSpeech();
  const [listenLanguage, setListenLanguage] = useState(lang || user.preferred_language?.code || "en");
  useEffect(() => setListenLanguage(lang), [lang]); // follows the app language

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
    if (!blob.type.startsWith("image/")) return toast.error(t("photo.choose"));
    if (blob.size > MAX_MB * 1024 * 1024) return toast.error(t("photo.tooBig", { mb: MAX_MB }));
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
        title={t("nav.items")}
        subtitle={t("items.subtitle")}
        actions={
          <button className="btn btn-ghost" onClick={newScan} disabled={!file && !result}>
            <Plus size={18} /> {t("photo.newScan")}
          </button>
        }
      />
      <div className="grid-2">
        <Card title={t("items.photo")} icon={ImagePlus}>
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
                  <img src={preview} alt={t("items.photo")} />
                ) : (
                  <div className="dropzone-empty">
                    <PackageSearch size={36} />
                    <p>{t("items.tapToChoose")}</p>
                    <p className="muted small">{t("items.labelFacing")} · {t("photo.formats", { mb: MAX_MB })}</p>
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
                  <Camera size={18} /> {t("photo.useCamera")}
                </button>
                <button className="btn btn-primary" onClick={identify} disabled={!file || busy}>
                  {busy ? <Spinner label={t("items.reading")} size={16} /> : (<><ScanLine size={18} /> {t("items.identify")}</>)}
                </button>
              </div>
            </>
          )}
        </Card>
        <Card title={t("items.whatIs")} icon={FlaskConical}>
          {result ? (
            <ItemResult item={result} listenLanguage={listenLanguage} onLanguage={setListenLanguage} />
          ) : (
            <EmptyState icon={PackageSearch} title={t("items.none")}>
              {t("items.chooseThenIdentify")}
            </EmptyState>
          )}
        </Card>
      </div>
    </div>
  );
}
