// Small player shown on every page while an answer is being spoken.
import { Link, useLocation } from "react-router-dom";
import { Pause, Play, Square, Volume2 } from "lucide-react";
import { useSpeech } from "../context/SpeechContext";
import { useI18n } from "../i18n";

export default function NowPlaying() {
  const speech = useSpeech();
  const { t } = useI18n();
  const { pathname } = useLocation();
  if (speech.id === null) return null;
  return (
    <div className="now-playing" role="region" aria-label={t("speech.spokenAnswer")}>
      <Volume2 size={18} aria-hidden className="now-playing-icon" />
      <div className="now-playing-text">
        <strong>{speech.playing ? t("speech.speaking") : t("speech.paused")}</strong>
        <span className="small">
          {t("speech.part", { i: Math.min(speech.index + 1, speech.total), n: speech.total })}
          {speech.label ? ` · ${speech.label}` : ""}
        </span>
      </div>
      <button className="icon-btn" onClick={speech.toggle} aria-label={speech.playing ? t("speech.pause") : t("speech.listen")}>
        {speech.playing ? <Pause size={18} /> : <Play size={18} />}
      </button>
      <button className="icon-btn" onClick={speech.stop} aria-label={t("speech.stop")}>
        <Square size={16} />
      </button>
      {pathname !== "/assistant" && speech.id?.startsWith?.("answer-") && (
        <Link to="/assistant" className="now-playing-link">{t("speech.openChat")}</Link>
      )}
    </div>
  );
}
