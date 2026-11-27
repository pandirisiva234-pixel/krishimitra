// Small chart building blocks shared by the farmer dashboard and the admin overview.
import { Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useI18n } from "../i18n";
import { EmptyState } from "./ui";

export const COLORS = ["#1f6b3a", "#d9822b", "#3a7ca5", "#8a5a44", "#7a9a3a", "#b04a5a", "#5a5a8a", "#999999"];
export const OUTCOME_COLORS = { healthy: "#2e8b57", disease: "#c0392b", uncertain: "#d9a21b" };

/** "2026-11-20" -> "20 Nov" in the interface language */
export function shortDay(iso, lang) {
  return new Date(`${iso}T00:00:00`).toLocaleDateString(lang, { day: "numeric", month: "short" });
}

export function ChartBox({ data, height = 220, children, emptyText }) {
  const { t } = useI18n();
  const hasData = data?.some((d) => (d.count ?? d.value ?? 0) > 0);
  if (!hasData) return <EmptyState title={emptyText || t("charts.noData")} />;
  return (
    <div className="chart">
      <ResponsiveContainer width="100%" height={height}>
        {children}
      </ResponsiveContainer>
    </div>
  );
}

/** Donut with the total in the middle and a legend underneath. */
export function Donut({ data, colors, height = 220, centerLabel }) {
  const total = data.reduce((s, d) => s + d.count, 0);
  return (
    <div className="donut">
      <ChartBox data={data} height={height}>
        <PieChart>
          <Pie data={data} dataKey="count" nameKey="name" innerRadius="58%" outerRadius="85%" paddingAngle={2} stroke="none">
            {data.map((d, i) => (
              <Cell key={d.name} fill={colors?.[d.key] || COLORS[i % COLORS.length]} />
            ))}
          </Pie>
          <Tooltip />
        </PieChart>
      </ChartBox>
      {total > 0 && (
        <>
          <div className="donut-center" style={{ height }}>
            <strong>{total}</strong>
            {centerLabel && <span>{centerLabel}</span>}
          </div>
          <ul className="legend">
            {data.map((d, i) => (
              <li key={d.name}>
                <span className="swatch" style={{ background: colors?.[d.key] || COLORS[i % COLORS.length] }} />
                {d.name} <strong>{d.count}</strong>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}

/** Ring gauge for a percentage (0-100). */
export function Gauge({ value, label, color = "#1f6b3a", suffix = "%", display }) {
  const v = value == null ? null : Math.max(0, Math.min(100, value));
  const data = [{ count: v ?? 0 }, { count: 100 - (v ?? 0) }];
  return (
    <div className="gauge">
      <ResponsiveContainer width="100%" height={130}>
        <PieChart>
          <Pie data={data} dataKey="count" startAngle={210} endAngle={-30} innerRadius="70%" outerRadius="95%" stroke="none">
            <Cell fill={color} />
            <Cell fill="var(--line)" />
          </Pie>
        </PieChart>
      </ResponsiveContainer>
      <div className="gauge-value">{v == null ? "—" : display ?? `${value}${suffix}`}</div>
      <div className="gauge-label">{label}</div>
    </div>
  );
}

export function DayBars({ data, lang, name, color = "#1f6b3a", height = 220 }) {
  const rows = data.map((d) => ({ ...d, day: shortDay(d.label, lang) }));
  return (
    <ChartBox data={data} height={height}>
      <BarChart data={rows} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" vertical={false} />
        <XAxis dataKey="day" tick={{ fontSize: 11 }} interval="preserveStartEnd" />
        <YAxis allowDecimals={false} tick={{ fontSize: 11 }} width={30} />
        <Tooltip />
        <Bar dataKey="count" name={name} fill={color} radius={[4, 4, 0, 0]} />
      </BarChart>
    </ChartBox>
  );
}
