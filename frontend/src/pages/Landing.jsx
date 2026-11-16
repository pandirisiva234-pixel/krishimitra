import { Link } from "react-router-dom";
import Logo from "../components/Logo";
import ThemeSwitch from "../components/ThemeSwitch";
import { BookOpen, CloudSun, Languages, Leaf, Mic, ShieldCheck, Sparkles } from "lucide-react";

const FEATURES = [
  { icon: Mic, title: "Ask by voice", text: "Speak your question in Telugu, Hindi, Kannada, Tamil, English and 5 more Indian languages, and hear the answer." },
  { icon: Leaf, title: "Check a leaf", text: "Take a photo of a sick leaf to see the likely disease, how sure the model is, and what to do." },
  { icon: BookOpen, title: "Answers with sources", text: "Advice comes from agricultural documents, and each answer shows where it came from." },
  { icon: CloudSun, title: "Weather for your farm", text: "5-day forecast with spraying, irrigation and disease-risk advice for your location." },
  { icon: Languages, title: "Your language", text: "Questions are understood and answers are spoken in the language you choose." },
  { icon: ShieldCheck, title: "Honest when unsure", text: "If the documents do not cover a question, it says so and points you to your KVK." },
];

const STATS = [
  { value: "5", label: "Indian languages, by voice" },
  { value: "99.4%", label: "Leaf-disease test accuracy" },
  { value: "9", label: "Official farming guides (ICAR, NIPHM, PPQS)" },
  { value: "~20 s", label: "Time to a cited answer" },
];

export default function Landing() {
  return (
    <div className="landing-page">
      <div className="landing-strip">
        <div className="landing-strip-inner">
          <span>
            <span className="dot" aria-hidden />
            <strong>KRISHIMITRA</strong> | Multilingual farming assistant
          </span>
          <span className="landing-strip-right">
            తెలుగు · हिन्दी · ಕನ್ನಡ · தமிழ் · English <ThemeSwitch onDark />
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
              Register
            </Link>
            <Link to="/login" className="btn btn-primary">
              Farmer login →
            </Link>
          </div>
        </div>
      </header>

      <div className="hero-band">
        <section className="hero">
          <div className="hero-text">
            <span className="hero-badge">
              <Sparkles size={14} aria-hidden /> AI farming assistant for Indian farmers
            </span>
            <h1>
              Ask about your crop in <span className="gold">your own language.</span>
            </h1>
            <p className="lead">
              KrishiMitra listens to your question, finds the answer in trusted agricultural guides, and speaks it back.
              It can also look at a photo of a leaf and suggest what disease it may have.
            </p>
            <div className="hero-actions">
              <Link to="/register" className="btn btn-gold btn-large">
                Get started, it's free
              </Link>
              <Link to="/login" className="btn btn-outline-light btn-large">
                I already have an account
              </Link>
            </div>
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
          <div key={s.label} className="landing-stat">
            <strong>{s.value}</strong>
            <span>{s.label}</span>
          </div>
        ))}
      </div>

      <div className="landing">
        <div className="section-title">
          <h2 className="welcome-title" style={{ color: "var(--green-900)" }}>What KrishiMitra does</h2>
          <p>Built for farmers who prefer speaking to typing.</p>
        </div>
        <section className="features">
          {FEATURES.map(({ icon: Icon, title, text }) => (
            <div key={title} className="feature">
              <span className="feature-icon">
                <Icon size={22} aria-hidden />
              </span>
              <h3>{title}</h3>
              <p>{text}</p>
            </div>
          ))}
        </section>
      </div>

      <footer className="landing-footer">
        <div className="landing-foot">
          <p>
            KrishiMitra gives general guidance. For serious crop problems, contact your nearest Krishi Vigyan Kendra or
            call the Kisan Call Centre at 1800-180-1551.
          </p>
          <p className="muted small">MCA Data Science project · Chanakya University</p>
        </div>
      </footer>
    </div>
  );
}
