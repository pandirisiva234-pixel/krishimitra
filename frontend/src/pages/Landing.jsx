import { Link } from "react-router-dom";
import Logo from "../components/Logo";
import ThemeSwitch from "../components/ThemeSwitch";
import { BookOpen, CloudSun, Languages, Leaf, Mic, ShieldCheck, Sparkles } from "lucide-react";
import { useI18n } from "../i18n";
import UiLanguageSwitch from "../components/UiLanguageSwitch";
import { DemoVideoButton, DemoVideoModal } from "../components/DemoVideo";
import { useState } from "react";

const FEATURES = [
  { icon: Mic, key: "voice" },
  { icon: Leaf, key: "leaf" },
  { icon: BookOpen, key: "sources" },
  { icon: CloudSun, key: "weather" },
  { icon: Languages, key: "language" },
  { icon: ShieldCheck, key: "honest" },
];

const STATS = [
  { value: "10", key: "languages" },
  { value: "99.4%", key: "accuracy" },
  { value: "11", key: "guides" },
  { value: "~15 s", key: "time" },
];

export default function Landing() {
  const { t } = useI18n();
  const [demo, setDemo] = useState(false);
  return (
    <div className="landing-page">
      <div className="landing-strip">
        <div className="landing-strip-inner">
          <span>
            <span className="dot" aria-hidden />
            <strong>KRISHIMITRA</strong> | {t("landing.strip")}
          </span>
          <span className="landing-strip-right">
            <UiLanguageSwitch onDark /> <ThemeSwitch onDark />
          </span>
        </div>
      </div>

      <header className="landing-header">
        <div className="landing-nav">
          <div className="brand">
            <Logo size={46} />
          </div>
          <div className="landing-nav-actions">
            <Link to="/register" className="btn btn-ghost">
              {t("register.button")}
            </Link>
            <Link to="/login" className="btn btn-primary">
              {t("landing.login")} →
            </Link>
          </div>
        </div>
      </header>

      <div className="hero-band">
        <section className="hero">
          <div className="hero-text">
            <span className="hero-badge">
              <Sparkles size={14} aria-hidden /> {t("landing.badge")}
            </span>
            <h1>
              {t("landing.heroA")} <span className="gold">{t("landing.heroB")}</span>
            </h1>
            <p className="lead">
              {t("landing.lead")}
            </p>
            <div className="hero-actions">
              <Link to="/register" className="btn btn-gold btn-large">
                {t("landing.start")}
              </Link>
              <Link to="/login" className="btn btn-outline-light btn-large">
                {t("landing.haveAccount")}
              </Link>
              <DemoVideoButton onClick={() => setDemo(true)} className="btn btn-outline-light btn-large" />
            </div>
            <DemoVideoModal open={demo} onClose={() => setDemo(false)} />
          </div>
          <div className="hero-card" aria-hidden>
            <div className="bubble bubble-user">టమాటా ఆకులపై మచ్చలు ఉన్నాయి, ఏమి చేయాలి?</div>
            <div className="bubble bubble-bot">
              Remove the spotted lower leaves and spray as per the label. <span className="cite">[1]</span>
              <div className="bubble-source">Source: Tomato package of practices, p. 12</div>
            </div>
            <div className="hero-mic">
              <Mic size={26} />
            </div>
          </div>
        </section>
      </div>

      <div className="landing-stats">
        {STATS.map((s) => (
          <div key={s.key} className="landing-stat">
            <strong>{s.value}</strong>
            <span>{t(`landing.stat.${s.key}`)}</span>
          </div>
        ))}
      </div>

      <div className="landing">
        <div className="section-title">
          <h2 className="welcome-title" style={{ color: "var(--green-900)" }}>{t("landing.what")}</h2>
          <p>{t("landing.builtFor")}</p>
        </div>
        <section className="features">
          {FEATURES.map(({ icon: Icon, key }) => (
            <div key={key} className="feature">
              <span className="feature-icon">
                <Icon size={22} aria-hidden />
              </span>
              <h3>{t(`landing.f.${key}.title`)}</h3>
              <p>{t(`landing.f.${key}.text`)}</p>
            </div>
          ))}
        </section>
      </div>

      <footer className="landing-footer">
        <div className="landing-foot">
          <p>
            {t("landing.footer")}
          </p>
          <p className="muted small">{t("landing.project")}</p>
        </div>
      </footer>
    </div>
  );
}
