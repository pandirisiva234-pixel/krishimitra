import { useCallback, useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Activity, BookOpen, Cpu, Leaf, MessageSquare, ThumbsUp, UserCheck, Users } from "lucide-react";
import { errorMessage } from "../../api/client";
import { admin } from "../../api/endpoints";
import { Card, EmptyState, ErrorBanner, PageHeader, PageLoader, StatCard } from "../../components/ui";
import { intentLabel } from "../../utils/format";

const COLORS = ["#1f6b3a", "#d9822b", "#3a7ca5", "#8a5a44", "#7a9a3a", "#b04a5a", "#5a5a8a", "#999"];

function ChartOrEmpty({ data, children, height = 260 }) {
  if (!data?.length) return <EmptyState title="No data yet for this period" />;
  return (
    <div className="chart">
      <ResponsiveContainer width="100%" height={height}>
        {children}
      </ResponsiveContainer>
    </div>
  );
}

function SystemStatus({ status }) {
  const rows = [
    ["PostgreSQL", status.database],
    ["Vector store (ChromaDB)", `${status.vector_store}${status.vector_chunks != null ? ` · ${status.vector_chunks} chunks` : ""}`],
    ["Gemini", status.gemini_configured ? `configured · ${status.gemini_model}` : "API key missing"],
    ["OpenWeather", status.openweather_configured ? "configured" : "API key missing"],
    ["Disease model", status.disease_model_available ? "available" : "not trained/copied yet"],
    ["Intent model", status.intent_model_available ? "trained model" : "keyword rules"],
    ["Models in memory", Object.entries(status.models_loaded).filter(([, v]) => v).map(([k]) => k).join(", ") || "none yet (load on first use)"],
    ["Disk free", `${status.disk_free_gb} GB · storage used ${status.storage_used_mb} MB`],
  ];
  return (
    <table className="table compact">
      <tbody>
        {rows.map(([k, v]) => (
          <tr key={k}>
            <th>{k}</th>
            <td>{v}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default function AdminDashboard() {
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
  const intents = stats.intent_distribution.map((i) => ({ ...i, label: intentLabel(i.label) }));

  return (
    <div>
      <PageHeader
        title="Admin overview"
        subtitle="Live numbers from the database."
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
        <StatCard label="Registered farmers" value={dash.total_farmers} hint={`+${dash.new_users_30d} new in 30 days`} icon={Users} />
        <StatCard label="Active users (7 days)" value={dash.active_users_7d} icon={UserCheck} tone="blue" />
        <StatCard label="Total questions" value={dash.total_queries} hint={`${dash.queries_today} today`} icon={MessageSquare} tone="amber" />
        <StatCard label="Disease scans" value={dash.total_disease_scans} icon={Leaf} tone="leaf" />
        <StatCard label="Indexed documents" value={dash.total_documents} icon={BookOpen} />
        <StatCard label="Helpful answers" value={dash.helpful_feedback_pct != null ? `${dash.helpful_feedback_pct}%` : "—"} hint="from farmer feedback" icon={ThumbsUp} tone="blue" />
        <StatCard label="Answers from sources" value={stats.grounded_answer_pct != null ? `${stats.grounded_answer_pct}%` : "—"} icon={BookOpen} tone="amber" />
        <StatCard label="Avg response time" value={stats.avg_response_ms != null ? `${(stats.avg_response_ms / 1000).toFixed(1)} s` : "—"} icon={Activity} tone="leaf" />
      </div>

      <div className="grid-2">
        <Card title="Questions per day" icon={Activity}>
          <ChartOrEmpty data={stats.queries_per_day}>
            <LineChart data={stats.queries_per_day}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" />
              <XAxis dataKey="label" tick={{ fontSize: 11 }} />
              <YAxis allowDecimals={false} tick={{ fontSize: 11 }} width={36} />
              <Tooltip />
              <Line dataKey="count" name="Questions" stroke="#1f6b3a" strokeWidth={2} />
            </LineChart>
          </ChartOrEmpty>
        </Card>
        <Card title="Language usage" icon={MessageSquare}>
          <ChartOrEmpty data={stats.language_usage}>
            <PieChart>
              <Pie data={stats.language_usage} dataKey="count" nameKey="label" outerRadius={95} label>
                {stats.language_usage.map((_, i) => (
                  <Cell key={i} fill={COLORS[i % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ChartOrEmpty>
        </Card>
        <Card title="Question topics (intents)" icon={MessageSquare}>
          <ChartOrEmpty data={intents}>
            <BarChart data={intents} layout="vertical" margin={{ left: 30 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" />
              <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11 }} />
              <YAxis type="category" dataKey="label" tick={{ fontSize: 11 }} width={120} />
              <Tooltip />
              <Bar dataKey="count" name="Questions" fill="#d9822b" />
            </BarChart>
          </ChartOrEmpty>
        </Card>
        <Card title="Most detected diseases" icon={Leaf}>
          <ChartOrEmpty data={stats.disease_distribution}>
            <BarChart data={stats.disease_distribution} layout="vertical" margin={{ left: 30 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" />
              <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11 }} />
              <YAxis type="category" dataKey="label" tick={{ fontSize: 11 }} width={160} />
              <Tooltip />
              <Bar dataKey="count" name="Scans" fill="#1f6b3a" />
            </BarChart>
          </ChartOrEmpty>
        </Card>
        <Card title="System status" icon={Cpu}>
          <SystemStatus status={system} />
        </Card>
        <Card title="Voice vs typed" icon={MessageSquare}>
          <ChartOrEmpty data={stats.input_modes} height={200}>
            <BarChart data={stats.input_modes}>
              <XAxis dataKey="label" />
              <YAxis allowDecimals={false} width={36} />
              <Tooltip />
              <Bar dataKey="count" name="Questions" fill="#3a7ca5" />
            </BarChart>
          </ChartOrEmpty>
        </Card>
      </div>
    </div>
  );
}
