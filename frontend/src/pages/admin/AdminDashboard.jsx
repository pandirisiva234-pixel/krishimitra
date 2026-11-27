// Admin overview: a few headline numbers, then charts. System health is shown as status lights.
import { useCallback, useEffect, useState } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Activity, Cpu, Gauge as GaugeIcon, Leaf, MessageSquare, ThumbsUp, UserPlus, Users } from "lucide-react";
import { errorMessage } from "../../api/client";
import { admin } from "../../api/endpoints";
import { ChartBox, COLORS, DayBars, Donut, Gauge, OUTCOME_COLORS, shortDay } from "../../components/Charts";
import { Card, ErrorBanner, PageHeader, PageLoader, StatCard } from "../../components/ui";
import { useI18n } from "../../i18n";

const FEEDBACK_COLORS = { helpful: "#2e8b57", not_helpful: "#c0392b" };

function StatusLights({ status }) {
  const lights = [
    ["Database", status.database === "ok", "PostgreSQL"],
    ["Knowledge store", status.vector_store === "ok", status.vector_chunks != null ? `${status.vector_chunks} chunks` : "ChromaDB"],
    ["Gemini AI", status.gemini_configured, status.gemini_model || "API key missing"],
    ["Weather", status.openweather_configured, "OpenWeather"],
    ["Disease model", status.disease_model_available, status.disease_model_available ? "ready" : "missing"],
    ["Intent model", status.intent_model_available, status.intent_model_available ? "trained" : "keyword rules"],
  ];
  const used = status.storage_used_mb;
  return (
    <div>
      <ul className="status-lights">
        {lights.map(([name, ok, detail]) => (
          <li key={name} className={ok ? "ok" : "bad"} title={detail}>
            <span className="light" aria-hidden />
            <span className="status-name">{name}</span>
            <span className="status-detail">{detail}</span>
          </li>
        ))}
      </ul>
      <p className="muted small">
        Disk free {status.disk_free_gb} GB · app storage {used} MB
      </p>
    </div>
  );
}

export default function AdminDashboard() {
  const { t, lang } = useI18n();
  const [days, setDays] = useState(30);
  const [state, setState] = useState(null);
  const [error, setError] = useState(null);

  const load = useCallback(() => {
    setError(null);
    Promise.all([admin.dashboard(), admin.statistics(days), admin.system()])
      .then(([dash, stats, system]) => setState({ dash, stats, system }))
      .catch((e) => setError(errorMessage(e)));
  }, [days]);
  useEffect(load, [load]);

  if (error) return <ErrorBanner message={error} onRetry={load} />;
  if (!state) return <PageLoader label="Loading statistics…" />;
  const { dash, stats, system } = state;
  const intents = stats.intent_distribution.map((i) => ({ ...i, label: t(`intent.${i.label}`) }));
  const languages = stats.language_usage.map((l) => ({ name: l.label, count: l.count }));
  const modes = stats.input_modes.map((m) => ({ name: m.label === "voice" ? "Spoken" : "Typed", count: m.count }));
  const feedback = (stats.feedback || []).map((f) => ({
    key: f.label,
    name: f.label === "helpful" ? "Helpful" : "Not helpful",
    count: f.count,
  }));
  const scans = (stats.scan_outcomes || []).map((s) => ({ key: s.label, name: t(`scan.${s.label}`), count: s.count }));
  const speed = (stats.response_seconds_per_day || []).map((d) => ({ ...d, day: shortDay(d.label, lang) }));
  const avgSeconds = stats.avg_response_ms != null ? +(stats.avg_response_ms / 1000).toFixed(1) : null;

  return (
    <div className="admin-overview">
      <PageHeader
        title="Admin overview"
        actions={
          <select className="select" value={days} onChange={(e) => setDays(Number(e.target.value))} aria-label="Period">
            <option value={7}>Last 7 days</option>
            <option value={30}>Last 30 days</option>
            <option value={90}>Last 90 days</option>
            <option value={365}>Last year</option>
          </select>
        }
      />

      <div className="stats-grid">
        <StatCard label="Farmers" value={dash.total_farmers} hint={`+${dash.new_users_30d} in 30 days`} icon={Users} />
        <StatCard label="Active (7 days)" value={dash.active_users_7d} icon={Activity} tone="blue" />
        <StatCard label="Questions" value={dash.total_queries} hint={`${dash.queries_today} today`} icon={MessageSquare} tone="amber" />
        <StatCard label="Leaf scans" value={dash.total_disease_scans} hint={`${dash.total_documents} documents`} icon={Leaf} tone="leaf" />
      </div>

      <div className="gauge-row">
        <Card>
          <Gauge value={stats.grounded_answer_pct} label="Answers from documents" color="#1f6b3a" />
        </Card>
        <Card>
          <Gauge value={dash.helpful_feedback_pct} label="Helpful (farmer votes)" color="#3a7ca5" />
        </Card>
        <Card>
          <Gauge
            value={avgSeconds == null ? null : Math.min(100, Math.round((avgSeconds / 60) * 100))}
            display={avgSeconds == null ? null : `${avgSeconds} s`}
            label="Average answer time (ring = share of 1 minute)"
            color={avgSeconds != null && avgSeconds > 30 ? "#c0392b" : "#d9822b"}
          />
        </Card>
      </div>

      <div className="grid-2">
        <Card title="Questions per day" icon={Activity}>
          <DayBars data={stats.queries_per_day} lang={lang} name="Questions" />
        </Card>
        <Card title="New farmers per day" icon={UserPlus}>
          <DayBars data={stats.registrations_per_day || []} lang={lang} name="Registrations" color="#3a7ca5" />
        </Card>
        <Card title="Languages used" icon={MessageSquare}>
          <Donut data={languages} centerLabel="questions" />
        </Card>
        <Card title="Question topics" icon={MessageSquare}>
          <ChartBox data={intents} height={240}>
            <BarChart data={intents} layout="vertical" margin={{ left: 10, right: 16 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" horizontal={false} />
              <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11 }} />
              <YAxis type="category" dataKey="label" tick={{ fontSize: 11 }} width={120} />
              <Tooltip />
              <Bar dataKey="count" name="Questions" radius={[0, 4, 4, 0]}>
                {intents.map((_, i) => (
                  <Cell key={i} fill={COLORS[i % COLORS.length]} />
                ))}
              </Bar>
            </BarChart>
          </ChartBox>
        </Card>
        <Card title="Answer time per day (seconds)" icon={GaugeIcon}>
          <ChartBox data={speed} height={220}>
            <AreaChart data={speed} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" vertical={false} />
              <XAxis dataKey="day" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} width={30} unit="s" />
              <Tooltip />
              <Area dataKey="value" name="Average seconds" stroke="#d9822b" fill="#d9822b" fillOpacity={0.25} strokeWidth={2} />
            </AreaChart>
          </ChartBox>
        </Card>
        <Card title="Spoken vs typed" icon={MessageSquare}>
          <Donut data={modes} centerLabel="questions" />
        </Card>
        <Card title="Leaf scan results" icon={Leaf}>
          <Donut data={scans} colors={OUTCOME_COLORS} centerLabel="scans" />
        </Card>
        <Card title="Farmer feedback" icon={ThumbsUp}>
          <Donut data={feedback} colors={FEEDBACK_COLORS} centerLabel="votes" />
        </Card>
        <Card title="Most detected diseases" icon={Leaf}>
          <ChartBox data={stats.disease_distribution} height={240}>
            <BarChart data={stats.disease_distribution} layout="vertical" margin={{ left: 10, right: 16 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" horizontal={false} />
              <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11 }} />
              <YAxis type="category" dataKey="label" tick={{ fontSize: 11 }} width={160} />
              <Tooltip />
              <Bar dataKey="count" name="Scans" fill="#1f6b3a" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ChartBox>
        </Card>
        <Card title="System health" icon={Cpu}>
          <StatusLights status={system} />
        </Card>
      </div>
    </div>
  );
}

