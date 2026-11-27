import { CloudSun, FileText, IndianRupee } from "lucide-react";
import { useI18n } from "../i18n";

export default function SourceList({ sources }) {
  const { t } = useI18n();
  if (!sources?.length) return null;
  return (
    <details className="sources">
      <summary>
        {t("sources.count", { n: sources.length })}
      </summary>
      <ol>
        {sources.map((s) => (
          <li key={`${s.index}-${s.title}`}>
            {s.kind === "weather" ? (
              <CloudSun size={14} aria-hidden />
            ) : s.kind === "market" ? (
              <IndianRupee size={14} aria-hidden />
            ) : (
              <FileText size={14} aria-hidden />
            )}
            <strong>
              [{s.index}] {s.title}
              {s.page ? `, ${t("kb.page")} ${s.page}` : ""}
            </strong>
            <p className="muted small">{s.snippet}</p>
          </li>
        ))}
      </ol>
    </details>
  );
}
