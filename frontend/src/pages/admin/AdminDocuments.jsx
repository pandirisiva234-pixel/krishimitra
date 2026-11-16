import { useCallback, useEffect, useRef, useState } from "react";
import { FileText, RefreshCw, Trash2, Upload } from "lucide-react";
import { errorMessage } from "../../api/client";
import { knowledge } from "../../api/endpoints";
import { Card, EmptyState, Field, PageHeader, Spinner } from "../../components/ui";
import { useToast } from "../../context/ToastContext";
import { formatDateTime } from "../../utils/format";

const MAX_MB = 25;

export default function AdminDocuments() {
  const toast = useToast();
  const [docs, setDocs] = useState(null);
  const [file, setFile] = useState(null);
  const [title, setTitle] = useState("");
  const [source, setSource] = useState("");
  const [busy, setBusy] = useState(false);
  const fileRef = useRef(null);

  const load = useCallback(() => knowledge.documents().then(setDocs).catch((e) => toast.error(errorMessage(e))), [toast]);
  useEffect(() => {
    load();
  }, [load]);

  // While anything is still being indexed, refresh every 3 seconds
  useEffect(() => {
    if (!docs?.some((d) => d.status === "processing")) return undefined;
    const t = setInterval(load, 3000);
    return () => clearInterval(t);
  }, [docs, load]);

  const upload = async (e) => {
    e.preventDefault();
    if (!file) return toast.error("Choose a PDF, TXT or MD file");
    if (file.size > MAX_MB * 1024 * 1024) return toast.error(`File is larger than ${MAX_MB} MB`);
    if (title.trim().length < 3) return toast.error("Give the document a title (3+ characters)");
    setBusy(true);
    try {
      await knowledge.upload(file, title.trim(), source.trim() || null);
      toast.success("Uploaded. Indexing has started.");
      setFile(null);
      setTitle("");
      setSource("");
      if (fileRef.current) fileRef.current.value = "";
      load();
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const remove = async (d) => {
    if (!window.confirm(`Delete “${d.title}” and remove it from search?`)) return;
    try {
      await knowledge.remove(d.id);
      toast.success("Document deleted");
      load();
    } catch (e) {
      toast.error(errorMessage(e));
    }
  };

  return (
    <div>
      <PageHeader
        title="Knowledge documents"
        subtitle="Upload trusted agricultural guides. Each is split into passages and indexed for the assistant."
        actions={
          <button className="btn btn-ghost" onClick={load}>
            <RefreshCw size={18} /> Refresh
          </button>
        }
      />
      <Card title="Upload a document" icon={Upload}>
        <form onSubmit={upload} className="form">
          <div className="grid-2">
            <Field label="File (PDF, TXT or MD)" htmlFor="doc-file" hint={`Up to ${MAX_MB} MB. Scanned PDFs need OCR first.`}>
              <input
                id="doc-file"
                ref={fileRef}
                type="file"
                accept=".pdf,.txt,.md"
                className="input"
                onChange={(e) => {
                  const f = e.target.files?.[0] || null;
                  setFile(f);
                  if (f && !title) setTitle(f.name.replace(/\.[^.]+$/, "").replace(/[_-]+/g, " "));
                }}
              />
            </Field>
            <Field label="Title" htmlFor="doc-title" hint="Shown to farmers as the source name">
              <input id="doc-title" className="input" value={title} onChange={(e) => setTitle(e.target.value)} />
            </Field>
            <Field label="Source URL (optional)" htmlFor="doc-src" hint="Where the document was downloaded from">
              <input id="doc-src" className="input" value={source} onChange={(e) => setSource(e.target.value)} />
            </Field>
          </div>
          <button className="btn btn-primary" disabled={busy}>
            {busy ? <Spinner label="Uploading…" size={16} /> : (<><Upload size={18} /> Upload and index</>)}
          </button>
        </form>
      </Card>

      <Card title="All documents" icon={FileText} className="mt">
        {!docs ? (
          <Spinner />
        ) : docs.length === 0 ? (
          <EmptyState icon={FileText} title="No documents yet">
            Upload crop guides (package of practices) from your State Agricultural University or ICAR.
          </EmptyState>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Title</th>
                  <th>File</th>
                  <th>Pages</th>
                  <th>Chunks</th>
                  <th>Status</th>
                  <th>Uploaded</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {docs.map((d) => (
                  <tr key={d.id}>
                    <td>{d.title}</td>
                    <td className="small">
                      {d.original_filename}
                      <div className="muted">{(d.file_size_bytes / 1e6).toFixed(1)} MB</div>
                    </td>
                    <td>{d.num_pages ?? "—"}</td>
                    <td>{d.num_chunks ?? "—"}</td>
                    <td>
                      <span className={`tag status-${d.status}`} title={d.error_message || ""}>
                        {d.status === "processing" ? <Spinner label="indexing" size={12} /> : d.status}
                      </span>
                      {d.error_message && <div className="field-msg small">{d.error_message}</div>}
                    </td>
                    <td>{formatDateTime(d.created_at)}</td>
                    <td>
                      <button className="icon-btn" aria-label={`Delete ${d.title}`} onClick={() => remove(d)}>
                        <Trash2 size={16} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
