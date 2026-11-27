import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { History as HistoryIcon, MessageSquare, Trash2 } from "lucide-react";
import { errorMessage } from "../api/client";
import { conversations } from "../api/endpoints";
import SourceList from "../components/SourceList";
import { AuthAudio, Card, EmptyState, ErrorBanner, PageHeader, PageLoader } from "../components/ui";
import { useToast } from "../context/ToastContext";
import { formatDateTime } from "../utils/format";
import { useI18n } from "../i18n";

export default function History() {
  const { t } = useI18n();
  const toast = useToast();
  const [list, setList] = useState(null);
  const [error, setError] = useState(null);
  const [selected, setSelected] = useState(null);

  const load = useCallback(() => {
    setError(null);
    conversations.list().then(setList).catch((e) => setError(errorMessage(e)));
  }, []);
  useEffect(load, [load]);

  const open = (id) =>
    conversations
      .get(id)
      .then(setSelected)
      .catch((e) => toast.error(errorMessage(e)));

  const remove = async (id) => {
    if (!window.confirm(t("history.confirmDelete"))) return;
    try {
      await conversations.remove(id);
      setList((l) => l.filter((c) => c.id !== id));
      if (selected?.id === id) setSelected(null);
      toast.success(t("history.deleted"));
    } catch (e) {
      toast.error(errorMessage(e));
    }
  };

  if (error) return <ErrorBanner message={error} onRetry={load} />;
  if (!list) return <PageLoader label={t("history.loading")} />;

  return (
    <div>
      <PageHeader title={t("history.title")} subtitle={t("history.subtitle")} />
      {list.length === 0 ? (
        <EmptyState icon={HistoryIcon} title={t("history.none")}>
          <Link to="/assistant">{t("assistant.firstQuestion")}</Link>
        </EmptyState>
      ) : (
        <div className="history-layout">
          <Card className="history-list">
            <ul className="list">
              {list.map((c) => (
                <li key={c.id} className={selected?.id === c.id ? "active" : ""}>
                  <button className="list-main link-btn" onClick={() => open(c.id)}>
                    {c.title}
                  </button>
                  <span className="list-meta">
                    {t("history.messages", { n: c.message_count })} · {c.language_code.toUpperCase()} ·{" "}
                    {formatDateTime(c.updated_at)}
                    <button className="icon-btn" aria-label={t("history.delete")} onClick={() => remove(c.id)}>
                      <Trash2 size={15} />
                    </button>
                  </span>
                </li>
              ))}
            </ul>
          </Card>
          <Card
            className="history-detail"
            title={selected ? selected.title : t("history.select")}
            icon={MessageSquare}
            actions={selected && <Link to={`/assistant?c=${selected.id}`} className="btn btn-small">{t("history.continue")}</Link>}
          >
            {selected ? (
              selected.messages.map((m) => (
                <div key={m.query_id} className="exchange">
                  <div className="bubble bubble-user">{m.question}</div>
                  <div className="bubble bubble-bot">
                    <p className="answer-text">{m.answer}</p>
                    <div className="answer-meta">
                      <span className="tag">{t(`intent.${m.intent || "other"}`)}</span>
                      <span className="muted small">
                        {m.input_mode === "voice" ? t("history.spoken") : t("history.typed")} · {formatDateTime(m.created_at)}
                      </span>
                    </div>
                    {m.audio_url && <AuthAudio url={m.audio_url} />}
                    <SourceList sources={m.sources} />
                  </div>
                </div>
              ))
            ) : (
              <p className="muted">{t("history.chooseLeft")}</p>
            )}
          </Card>
        </div>
      )}
    </div>
  );
}
