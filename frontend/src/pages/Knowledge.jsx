import { useEffect, useState } from "react";
import { BookOpen, ExternalLink, FileText, Search } from "lucide-react";
import { errorMessage } from "../api/client";
import { knowledge } from "../api/endpoints";
import LanguageSelect from "../components/LanguageSelect";
import { Card, EmptyState, PageHeader, Spinner } from "../components/ui";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import { formatDate } from "../utils/format";

export default function Knowledge() {
  const { user } = useAuth();
  const toast = useToast();
  const [docs, setDocs] = useState([]);
  const [query, setQuery] = useState("");
  const [language, setLanguage] = useState(user.preferred_language.code);
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
        title="Agricultural knowledge base"
        subtitle="Search the guides the assistant reads. These passages are exactly what answers are built from."
      />
      <Card>
        <form className="search-row" onSubmit={search}>
          <LanguageSelect value={language} onChange={setLanguage} />
          <input
            className="input"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="e.g. gypsum for groundnut, paddy stem borer control"
          />
          <button className="btn btn-primary" disabled={busy}>
            {busy ? <Spinner label="Searching…" size={16} /> : (<><Search size={18} /> Search</>)}
          </button>
        </form>
      </Card>

      {results && (
        <Card title={`Results for “${results.query_english}”`} className="mt">
          {results.results.length ? (
            <ol className="passages">
              {results.results.map((r) => (
                <li key={`${r.document_id}-${r.index}`}>
                  <div className="passage-head">
                    <FileText size={16} /> <strong>{r.title}</strong>
                    {r.page && <span className="muted"> · page {r.page}</span>}
                    <span className="tag">relevance {r.score?.toFixed(2)}</span>
                  </div>
                  <p>{r.snippet}</p>
                </li>
              ))}
            </ol>
          ) : (
            <p className="muted">Nothing relevant found. Try other words, or ask the admin to add documents on this topic.</p>
          )}
        </Card>
      )}

      <Card title={`Documents (${indexed.length})`} icon={BookOpen} className="mt">
        {indexed.length ? (
          <table className="table">
            <thead>
              <tr>
                <th>Title</th>
                <th>Pages</th>
                <th>Added</th>
                <th>Source</th>
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
                        Open <ExternalLink size={12} />
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
          <EmptyState icon={BookOpen} title="No documents yet">
            An administrator needs to upload agricultural PDFs first.
          </EmptyState>
        )}
      </Card>
    </div>
  );
}
