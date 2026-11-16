import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { AlertTriangle, CloudSun, Droplets, Leaf, MapPin, MessageSquare, Mic, Sprout, Thermometer, Wind } from "lucide-react";
import { errorMessage } from "../api/client";
import { dashboard, weather } from "../api/endpoints";
import { Card, EmptyState, ErrorBanner, PageLoader, StatCard } from "../components/ui";
import { useAuth } from "../context/AuthContext";
import { formatDateTime, intentLabel, kmh, pct, prettyLabel } from "../utils/format";

function WeatherSummary() {
  const [state, setState] = useState({ loading: true });
  useEffect(() => {
    Promise.all([weather.current(), weather.forecast()])
      .then(([current, forecast]) => setState({ current, forecast }))
      .catch((e) => setState({ error: errorMessage(e) }));
  }, []);
  if (state.loading) return <PageLoader label="Loading weather…" />;
  if (state.error) return <p className="muted">{state.error}</p>;
  const { current, forecast } = state;
  return (
    <div className="weather-mini">
      <div className="weather-now">
        <div className="weather-temp">{Math.round(current.temperature_c)}°C</div>
        <div>
          <div className="capitalize">{current.description}</div>
          <div className="muted small">
            <MapPin size={12} /> {current.location_name || "Your farm"}
          </div>
        </div>
      </div>
      <div className="weather-facts">
        <span>
          <Droplets size={14} /> {current.humidity_pct}%
        </span>
        <span>
          <Wind size={14} /> {kmh(current.wind_speed_ms)} km/h
        </span>
        <span>
          <Thermometer size={14} /> feels {Math.round(current.feels_like_c)}°
        </span>
      </div>
      <ul className="advisory-list">
        {forecast.advisories.slice(0, 3).map((a) => (
          <li key={a.title} className={`advisory advisory-${a.level}`}>
            <strong>{a.title}</strong>
            <span>{a.message}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function Dashboard() {
  const { user } = useAuth();
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  const load = useCallback(() => {
    setError(null);
    dashboard.summary().then(setData).catch((e) => setError(errorMessage(e)));
  }, []);
  useEffect(load, [load]);

  if (error) return <ErrorBanner message={error} onRetry={load} />;
  if (!data) return <PageLoader label="Loading your dashboard…" />;

  return (
    <div>
      <section className="welcome">
        <div>
          <span className="welcome-chip">
            <Sprout size={14} aria-hidden /> KrishiMitra · Farmer workspace
          </span>
          <h1 className="welcome-title">Namaste, {user.full_name}</h1>
          <p className="welcome-sub">
            {[user.district, user.state].filter(Boolean).join(", ") || "Set your farm location in Profile"}
            {user.preferred_language?.name && (
              <>
                {" "}· Language: <strong>{user.preferred_language.name}</strong>
              </>
            )}
          </p>
        </div>
        <div className="welcome-actions">
          <Link to="/disease" className="btn btn-outline-light btn-large">
            <Leaf size={20} /> Check a leaf
          </Link>
          <Link to="/assistant" className="btn btn-gold btn-large">
            <Mic size={20} /> Ask a question
          </Link>
        </div>
      </section>

      <div className="stats-grid">
        <StatCard label="Questions asked" value={data.total_queries} icon={MessageSquare} />
        <StatCard label="Spoken questions" value={data.voice_queries} icon={Mic} tone="amber" />
        <StatCard label="Conversations" value={data.total_conversations} icon={MessageSquare} tone="blue" />
        <StatCard label="Leaf scans" value={data.total_disease_scans} icon={Leaf} tone="leaf" />
      </div>

      <div className="grid-2 dashboard-grid">
        <Card title="Weather & farm advice" icon={CloudSun} actions={<Link to="/weather">Full forecast</Link>}>
          {data.has_location ? (
            <WeatherSummary />
          ) : (
            <EmptyState icon={MapPin} title="Set your farm location">
              <Link to="/profile">Add your location in Profile</Link> to see local weather and advice.
            </EmptyState>
          )}
        </Card>

        <Card title="Recent questions" icon={MessageSquare} actions={<Link to="/history">All history</Link>}>
          {data.recent_questions.length ? (
            <ul className="list">
              {data.recent_questions.map((q, i) => (
                <li key={i}>
                  <Link to={`/assistant?c=${q.conversation_id}`} className="list-main">
                    {q.question}
                  </Link>
                  <span className="list-meta">
                    <span className="tag">{intentLabel(q.intent)}</span> {formatDateTime(q.created_at)}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState icon={Mic} title="No questions yet">
              <Link to="/assistant">Ask your first question</Link>
            </EmptyState>
          )}
        </Card>

        <Card title="Recent leaf scans" icon={Leaf} actions={<Link to="/disease">Scan a leaf</Link>}>
          {data.recent_predictions.length ? (
            <ul className="list">
              {data.recent_predictions.map((p) => (
                <li key={p.id}>
                  <span className="list-main">{p.disease_name ? prettyLabel(p.label) : p.label}</span>
                  <span className="list-meta">
                    {p.is_uncertain ? (
                      <span className="tag tag-warn">
                        <AlertTriangle size={12} /> uncertain
                      </span>
                    ) : (
                      <span className="tag">{pct(p.confidence)}</span>
                    )}{" "}
                    {formatDateTime(p.created_at)}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState icon={Leaf} title="No scans yet">
              Take a photo of a sick leaf on the <Link to="/disease">Disease detection</Link> page.
            </EmptyState>
          )}
        </Card>

        <Card title="Tips for better answers" icon={Mic}>
          <ul className="tips">
            <li>Name the crop and what you see: "yellow spots on chilli leaves".</li>
            <li>Speak close to the phone in a quiet place; you can correct the text before asking.</li>
            <li>For leaf photos, use daylight and fill the frame with one leaf.</li>
            <li>Always read the product label before spraying any chemical.</li>
          </ul>
        </Card>
      </div>
    </div>
  );
}
