import { CloudSun, FileText } from "lucide-react";

export default function SourceList({ sources }) {
  if (!sources?.length) return null;
  return (
    <details className="sources">
      <summary>
        {sources.length} source{sources.length > 1 ? "s" : ""}
      </summary>
      <ol>
        {sources.map((s) => (
          <li key={`${s.index}-${s.title}`}>
            {s.kind === "weather" ? <CloudSun size={14} aria-hidden /> : <FileText size={14} aria-hidden />}
            <strong>
              [{s.index}] {s.title}
              {s.page ? `, p. ${s.page}` : ""}
            </strong>
            <p className="muted small">{s.snippet}</p>
          </li>
        ))}
      </ol>
    </details>
  );
}
