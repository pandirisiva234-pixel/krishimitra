import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { AlertTriangle, BarChart3, CloudSun, Droplets, Leaf, MapPin, MessageSquare, Mic, Sprout, Thermometer, Wind } from "lucide-react";
import { errorMessage } from "../api/client";
import { dashboard, weather } from "../api/endpoints";
import { Card, EmptyState, ErrorBanner, PageLoader, StatCard } from "../components/ui";
import { useAuth } from "../context/AuthContext";
import { formatDateTime, kmh, pct, prettyLabel } from "../utils/format";
import { useI18n } from "../i18n";
import AdvisoryList from "../components/AdvisoryList";
import { DayBars, Donut, OUTCOME_COLORS } from "../components/Charts";

function WeatherSummary() {
  const { t } = useI18n();
  const [state, setState] = useState({ loading: true });
  useEffect(() => {
    Promise.all([weather.current(), weather.forecast()])
      .then(([current, forecast]) => setState({ current, forecast }))
      .catch((e) => setState({ error: errorMessage(e) }));
  }, []);
  if (state.loading) return <PageLoader label={t("weather.loading")} />;
  if (state.error) return <p className="muted">{state.error}</p>;
  const { current, forecast } = state;
  return (
    <div className="weather-mini">
      <div className="weather-now">
        <div className="weather-temp">{Math.round(current.temperature_c)}°C</div>
        <div>
          <div className="capitalize">{current.description}</div>
          <div className="muted small">
            <MapPin size={12} /> {current.location_name || t("dash.yourFarm")}
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
          <Thermometer size={14} /> {t("weather.feels")} {Math.round(current.feels_like_c)}°
        </span>
      </div>
      <AdvisoryList advisories={forecast.advisories.slice(0, 3)} />
    </div>
  );
}

export default function Dashboard() {
  const { user } = useAuth();
  const { t, lang } = useI18n();
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  const load = useCallback(() => {
    setError(null);
    dashboard.summary().then(setData).catch((e) => setError(errorMessage(e)));
  }, []);
  useEffect(load, [load]);

  if (error) return <ErrorBanner message={error} onRetry={load} />;
  if (!data) return <PageLoader label={t("dash.loading")} />;

  return (
    <div>
      <section className="welcome">
        <div>
          <span className="welcome-chip">
            <Sprout size={14} aria-hidden /> KrishiMitra · {t("nav.farmerWorkspace")}
          </span>
          <h1 className="welcome-title">{t("dash.namaste", { name: user.full_name })}</h1>
          <p className="welcome-sub">
            {[user.district, user.state].filter(Boolean).join(", ") || t("dash.setLocationInProfile")}
            {user.preferred_language?.name && (
              <>
                {" "}· {t("dash.language")}: <strong>{user.preferred_language.name}</strong>
              </>
            )}
          </p>
        </div>
        <div className="welcome-actions">
          <Link to="/disease" className="btn btn-outline-light btn-large">
            <Leaf size={20} /> {t("dash.checkLeaf")}
          </Link>
          <Link to="/assistant" className="btn btn-gold btn-large">
            <Mic size={20} /> {t("dash.askQuestion")}
          </Link>
        </div>
      </section>

      <div className="stats-grid">
        <StatCard label={t("dash.questionsAsked")} value={data.total_queries} icon={MessageSquare} />
        <StatCard label={t("dash.spokenQuestions")} value={data.voice_queries} icon={Mic} tone="amber" />
        <StatCard label={t("dash.conversations")} value={data.total_conversations} icon={MessageSquare} tone="blue" />
        <StatCard label={t("dash.leafScans")} value={data.total_disease_scans} icon={Leaf} tone="leaf" />
      </div>

      <div className="grid-3 mt">
        <Card title={t("dash.chartActivity")} icon={BarChart3}>
          <DayBars data={data.activity_14d || []} lang={lang} name={t("dash.questionsAsked")} />
        </Card>
        <Card title={t("dash.chartTopics")} icon={MessageSquare}>
          <Donut
            data={(data.topics || []).map((d) => ({ name: t(`intent.${d.label}`), count: d.count }))}
            centerLabel={t("dash.questionsAsked")}
          />
        </Card>
        <Card title={t("dash.chartScans")} icon={Leaf}>
          <Donut
            data={(data.scan_outcomes || []).map((d) => ({ key: d.label, name: t(`scan.${d.label}`), count: d.count }))}
            colors={OUTCOME_COLORS}
            centerLabel={t("dash.leafScans")}
          />
        </Card>
      </div>

      <div className="grid-2 dashboard-grid">
        <Card title={t("dash.weatherAdvice")} icon={CloudSun} actions={<Link to="/weather">{t("dash.fullForecast")}</Link>}>
          {data.has_location ? (
            <WeatherSummary />
          ) : (
            <EmptyState icon={MapPin} title={t("dash.setLocation")}>
              <Link to="/profile">{t("dash.addLocation")}</Link> {t("dash.toSeeWeather")}
            </EmptyState>
          )}
        </Card>

        <Card title={t("dash.recentQuestions")} icon={MessageSquare} actions={<Link to="/history">{t("dash.allHistory")}</Link>}>
          {data.recent_questions.length ? (
            <ul className="list">
              {data.recent_questions.map((q, i) => (
                <li key={i}>
                  <Link to={`/assistant?c=${q.conversation_id}`} className="list-main">
                    {q.question}
                  </Link>
                  <span className="list-meta">
                    <span className="tag">{t(`intent.${q.intent || "other"}`)}</span> {formatDateTime(q.created_at)}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState icon={Mic} title={t("dash.noQuestions")}>
              <Link to="/assistant">{t("assistant.firstQuestion")}</Link>
            </EmptyState>
          )}
        </Card>

        <Card title={t("dash.recentScans")} icon={Leaf} actions={<Link to="/disease">{t("dash.scanLeaf")}</Link>}>
          {data.recent_predictions.length ? (
            <ul className="list">
              {data.recent_predictions.map((p) => (
                <li key={p.id}>
                  <span className="list-main">{p.disease_name ? prettyLabel(p.label) : p.label}</span>
                  <span className="list-meta">
                    {p.is_uncertain ? (
                      <span className="tag tag-warn">
                        <AlertTriangle size={12} /> {t("disease.uncertain")}
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
            <EmptyState icon={Leaf} title={t("dash.noScans")}>
              <Link to="/disease">{t("dash.takePhoto")}</Link>
            </EmptyState>
          )}
        </Card>

        <Card title={t("dash.tips")} icon={Mic}>
          <ul className="tips">
            <li>{t("dash.tip1")}</li>
            <li>{t("dash.tip2")}</li>
            <li>{t("dash.tip3")}</li>
            <li>{t("dash.tip4")}</li>
          </ul>
        </Card>
      </div>
    </div>
  );
}
