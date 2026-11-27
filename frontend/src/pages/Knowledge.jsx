import { useEffect, useState } from "react";
import { BookOpen, ExternalLink, FileText, Search } from "lucide-react";
import { errorMessage } from "../api/client";
import { knowledge } from "../api/endpoints";
import LanguageSelect from "../components/LanguageSelect";
import { Card, EmptyState, PageHeader, Spinner } from "../components/ui";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import { formatDate } from "../utils/format";
import { useI18n } from "../i18n";

export default function Knowledge() {
  const { user } = useAuth();
  const { t, lang } = useI18n();
  const toast = useToast();
  const [docs, setDocs] = useState([]);
  const [query, setQuery] = useState("");
  const [language, setLanguage] = useState(lang || user.preferred_language.code);
  const [results, setResults] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    knowledge.documents().then(setDocs).catch((e) => toast.error(errorMessage(e)));
  }, [toast]);

  const search = async (e) => {
    e.preventDefault();
    if (query.trim().length < 2) return;
    setBusy(true);
    try {
      setResults(await knowledge.search({ query: query.trim(), language_code: language, top_n: 5 }));
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const indexed = docs.filter((d) => d.status === "indexed");

  return (
    <div>
      <PageHeader
        title={t("kb.title")}
        subtitle={t("kb.subtitle")}
      />
      <Card>
        <form className="search-row" onSubmit={search}>
          <LanguageSelect value={language} onChange={setLanguage} />
          <input
            className="input"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={t("kb.placeholder")}
          />
          <button className="btn btn-primary" disabled={busy}>
            {busy ? <Spinner label={t("kb.searching")} size={16} /> : (<><Search size={18} /> {t("common.search")}</>)}
          </button>
        </form>
      </Card>

      {results && (
        <Card title={t("kb.results", { q: results.query_english })} className="mt">
          {results.results.length ? (
            <ol className="passages">
              {results.results.map((r) => (
                <li key={`${r.document_id}-${r.index}`}>
                  <div className="passage-head">
                    <FileText size={16} /> <strong>{r.title}</strong>
                    {r.page && <span className="muted"> · {t("kb.page")} {r.page}</span>}
                    <span className="tag">{t("kb.relevance")} {r.score?.toFixed(2)}</span>
                  </div>
                  <p>{r.snippet}</p>
                </li>
              ))}
            </ol>
          ) : (
            <p className="muted">{t("kb.nothing")}</p>
          )}
        </Card>
      )}

      <Card title={t("kb.documents", { n: indexed.length })} icon={BookOpen} className="mt">
        {indexed.length ? (
          <table className="table">
            <thead>
              <tr>
                <th>{t("kb.colTitle")}</th>
                <th>{t("kb.colPages")}</th>
                <th>{t("kb.colAdded")}</th>
                <th>{t("kb.colSource")}</th>
              </tr>
            </thead>
            <tbody>
              {indexed.map((d) => (
                <tr key={d.id}>
                  <td>{d.title}</td>
                  <td>{d.num_pages ?? "—"}</td>
                  <td>{formatDate(d.created_at)}</td>
                  <td>
                    {d.source_url ? (
                      <a href={d.source_url} target="_blank" rel="noreferrer">
                        {t("kb.open")} <ExternalLink size={12} />
                      </a>
                    ) : (
                      "—"
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <EmptyState icon={BookOpen} title={t("kb.noDocs")}>
            {t("kb.adminUpload")}
          </EmptyState>
        )}
      </Card>
    </div>
  );
}
