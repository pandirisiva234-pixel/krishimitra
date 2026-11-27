// Short step-by-step guide for first-time users, in the interface language. It opens once
// automatically for a new farmer and can be opened again from the "?" button in the top bar.
import { useEffect, useState } from "react";
import { BookOpen, CloudSun, HelpCircle, Leaf, Mic, PlayCircle, Sparkles, X } from "lucide-react";
import { useI18n } from "../i18n";
import UiLanguageSwitch from "./UiLanguageSwitch";
import { DemoVideoButton, DemoVideoPlayer } from "./DemoVideo";

const SEEN_KEY = "krishimitra_guide_seen";

export function guideSeen() {
  try {
    return localStorage.getItem(SEEN_KEY) === "1";
  } catch {
    return true; // without storage, do not keep opening it
  }
}

export function markGuideSeen() {
  try {
    localStorage.setItem(SEEN_KEY, "1");
  } catch {
    /* storage unavailable */
  }
}

const FARMER_STEPS = [
  { key: "welcome", icon: Sparkles, chooseLanguage: true },
  { key: "ask", icon: Mic },
  { key: "answer", icon: PlayCircle },
  { key: "leaf", icon: Leaf },
  { key: "weather", icon: CloudSun },
  { key: "help", icon: HelpCircle },
];

const ADMIN_STEPS = [
  { key: "adminOverview", icon: Sparkles },
  { key: "adminDocs", icon: BookOpen },
  { key: "help", icon: HelpCircle },
];

export default function UserGuide({ open, onClose, isAdmin = false }) {
  const { t } = useI18n();
  const steps = isAdmin ? ADMIN_STEPS : FARMER_STEPS;
  const [i, setI] = useState(0);
  const [video, setVideo] = useState(false);

  useEffect(() => {
    if (open) {
      setI(0);
      setVideo(false);
    }
  }, [open]);

  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;
  const step = steps[i];
  const Icon = step.icon;
  const last = i === steps.length - 1;

  if (video) {
    return (
      <div className="guide-backdrop" role="presentation" onClick={onClose}>
        <div className="guide guide-wide" role="dialog" aria-modal="true" aria-labelledby="guide-title" onClick={(e) => e.stopPropagation()}>
          <button className="icon-btn guide-close" onClick={onClose} aria-label={t("common.close")}>
            <X size={20} />
          </button>
          <h2 id="guide-title">{t("demo.title")}</h2>
          <DemoVideoPlayer />
          <div className="guide-actions">
            <button className="btn btn-ghost" onClick={() => setVideo(false)}>
              {t("demo.backToGuide")}
            </button>
            <button className="btn btn-primary" onClick={onClose}>
              {t("guide.done")}
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="guide-backdrop" role="presentation" onClick={onClose}>
      <div
        className="guide"
        role="dialog"
        aria-modal="true"
        aria-labelledby="guide-title"
        onClick={(e) => e.stopPropagation()}
      >
        <button className="icon-btn guide-close" onClick={onClose} aria-label={t("common.close")}>
          <X size={20} />
        </button>
        <div className="guide-icon" aria-hidden>
          <Icon size={34} />
        </div>
        <p className="guide-step">{t("guide.stepOf", { i: i + 1, n: steps.length })}</p>
        <h2 id="guide-title">{t(`guide.${step.key}.title`)}</h2>
        <p className="guide-text">{t(`guide.${step.key}.text`)}</p>
        {step.chooseLanguage && (
          <div className="guide-language">
            <span>{t("guide.chooseLanguage")}</span>
            <UiLanguageSwitch />
          </div>
        )}
        <DemoVideoButton onClick={() => setVideo(true)} />
        <div className="guide-dots" aria-hidden>
          {steps.map((s, n) => (
            <span key={s.key} className={n === i ? "on" : ""} />
          ))}
        </div>
        <div className="guide-actions">
          {i > 0 ? (
            <button className="btn btn-ghost" onClick={() => setI(i - 1)}>
              {t("guide.back")}
            </button>
          ) : (
            <button className="btn btn-ghost" onClick={onClose}>
              {t("guide.skip")}
            </button>
          )}
          <button className="btn btn-primary" onClick={() => (last ? onClose() : setI(i + 1))}>
            {last ? t("guide.done") : t("guide.next")}
          </button>
        </div>
      </div>
    </div>
  );
}
