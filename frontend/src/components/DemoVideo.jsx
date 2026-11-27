// Recorded walkthrough of the farmer app, one video per interface language
// (public/demo/krishimitra_demo_<lang>.mp4). Shown from the first-time guide, the "?" help and the home page.
import { useEffect } from "react";
import { PlayCircle, X } from "lucide-react";
import { useI18n } from "../i18n";

export const DEMO_LANGUAGES = ["en", "te", "hi", "kn", "ta", "ml", "mr", "bn", "gu", "ur"];

/** Video (and poster) in the app language; English when there is no video for it. */
export function demoVideoFor(lang) {
  const code = DEMO_LANGUAGES.includes(lang) ? lang : "en";
  return { src: `/demo/krishimitra_demo_${code}.mp4`, poster: `/demo/krishimitra_demo_${code}.jpg` };
}

export function DemoVideoPlayer({ autoPlay = true }) {
  const { t, lang } = useI18n();
  const { src, poster } = demoVideoFor(lang);
  return (
    <div className="demo-video">
      <video
        key={src}
        src={src}
        poster={poster}
        controls
        autoPlay={autoPlay}
        playsInline
        preload="metadata"
        aria-label={t("demo.title")}
      >
        <a href={src}>{t("demo.download")}</a>
      </video>
      <p className="muted small">{t("demo.note")}</p>
    </div>
  );
}

/** Button that opens the demo video. */
export function DemoVideoButton({ onClick, className = "link-btn demo-video-btn" }) {
  const { t } = useI18n();
  return (
    <button type="button" className={className} onClick={onClick}>
      <PlayCircle size={18} aria-hidden /> {t("demo.watch")}
    </button>
  );
}

/** Stand-alone pop-up with the video (used on the home page). */
export function DemoVideoModal({ open, onClose }) {
  const { t } = useI18n();
  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="guide-backdrop" role="presentation" onClick={onClose}>
      <div className="guide guide-wide" role="dialog" aria-modal="true" aria-labelledby="demo-title" onClick={(e) => e.stopPropagation()}>
        <button className="icon-btn guide-close" onClick={onClose} aria-label={t("common.close")}>
          <X size={20} />
        </button>
        <h2 id="demo-title">{t("demo.title")}</h2>
        <DemoVideoPlayer />
      </div>
    </div>
  );
}
