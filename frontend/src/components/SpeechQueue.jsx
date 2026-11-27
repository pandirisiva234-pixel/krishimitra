// Listen / Pause button for one answer. Playback itself is done by the app-wide player
// (SpeechContext), so it continues when the farmer moves to another page.
import { useEffect, useRef } from "react";
import { Pause, Play, Square, Volume2 } from "lucide-react";
import { useSpeech } from "../context/SpeechContext";
import { Spinner } from "./ui";
import { useI18n } from "../i18n";

export default function SpeechQueue({ id, chunks, languageCode, autoPlay = false, label = "", translate = false }) {
  const speech = useSpeech();
  const { t } = useI18n();
  const started = useRef(false);
  const current = speech.id === id;

  useEffect(() => {
    if (autoPlay && !started.current && !current && chunks?.length) {
      started.current = true;
      speech.play(id, chunks, languageCode, label, translate);
    }
  }, [autoPlay]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!chunks?.length) return null;
  if (!current) {
    return (
      <div className="speech-queue">
        <button className="btn btn-ghost btn-small" onClick={() => speech.play(id, chunks, languageCode, label, translate)}>
          <Play size={16} /> {t("speech.listen")}
        </button>
      </div>
    );
  }
  const waiting = speech.playing && speech.ready <= speech.index && !speech.failed;
  return (
    <div className="speech-queue">
      <button className="btn btn-ghost btn-small" onClick={speech.toggle} disabled={speech.ready === 0 && !speech.failed}>
        {speech.playing ? <Pause size={16} /> : <Play size={16} />} {speech.playing ? t("speech.pause") : t("speech.listen")}
      </button>
      <button className="btn btn-ghost btn-small" onClick={speech.stop} aria-label={t("speech.stop")}>
        <Square size={14} /> {t("speech.stop")}
      </button>
      <span className="muted small">
        <Volume2 size={14} aria-hidden /> {t("speech.part", { i: Math.min(speech.index + 1, speech.total), n: speech.total })}
      </span>
      {waiting && <Spinner label={t("speech.preparing")} size={14} />}
      {speech.failed && speech.ready === 0 && <span className="muted small">{t("speech.unavailable")}</span>}
    </div>
  );
}
