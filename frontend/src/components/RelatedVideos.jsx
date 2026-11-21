import { useEffect, useState } from "react";
import { BadgeCheck, PlayCircle, Youtube } from "lucide-react";
import { assistant } from "../api/endpoints";

const SKIP_INTENTS = new Set(["greeting", "weather"]);

export function formatDuration(seconds) {
  if (!seconds && seconds !== 0) return "";
  const m = Math.floor(seconds / 60);
  const s = String(seconds % 60).padStart(2, "0");
  return `${m}:${s}`;
}

/**
 * Up to 3 related YouTube videos under an answer.
 * A new answer (autoLoad) fetches them straight away; older answers show a button,
 * so opening the history does not use up the daily YouTube quota.
 * Hidden completely when the server has no YouTube key or nothing was found.
 */
export default function RelatedVideos({ question, original, languageCode, intent, autoLoad = false }) {
  const [state, setState] = useState({ status: "idle", videos: [] });
  const usable = question && !SKIP_INTENTS.has(intent);

  const load = async () => {
    setState({ status: "loading", videos: [] });
    try {
      const res = await assistant.videos(question, languageCode || "en", original);
      setState({ status: res?.enabled ? "done" : "off", videos: res?.videos || [] });
    } catch {
      setState({ status: "error", videos: [] }); // videos are optional: hide them quietly
    }
  };

  useEffect(() => {
    if (usable && autoLoad) load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [question, languageCode, intent, autoLoad]);

  if (!usable || state.status === "off" || state.status === "error") return null;
  if (state.status === "idle") {
    return (
      <button className="link-btn videos-toggle" onClick={load}>
        <Youtube size={14} aria-hidden /> Show related videos
      </button>
    );
  }
  if (state.status === "loading") {
    return <p className="muted small videos-loading"><Youtube size={14} aria-hidden /> Finding related videos…</p>;
  }
  if (!state.videos.length) return null;

  return (
    <section className="videos" aria-label="Related videos">
      <h4><Youtube size={15} aria-hidden /> Related videos</h4>
      <ul>
        {state.videos.map((v) => (
          <li key={v.video_id}>
            <a href={v.url} target="_blank" rel="noopener noreferrer" className="video-card">
              <span className="video-thumb">
                {v.thumbnail_url && <img src={v.thumbnail_url} alt="" loading="lazy" />}
                <PlayCircle className="video-play" size={28} aria-hidden />
                {v.duration_seconds ? <span className="video-time">{formatDuration(v.duration_seconds)}</span> : null}
              </span>
              <span className="video-info">
                <span className="video-title" dir="auto">{v.title}</span>
                <span className="video-channel muted small">
                  {v.channel}
                  {v.trusted && (
                    <span className="video-trusted" title="Official or extension channel">
                      <BadgeCheck size={13} aria-hidden /> Trusted
                    </span>
                  )}
                </span>
              </span>
            </a>
          </li>
        ))}
      </ul>
      <p className="muted small">Videos are from YouTube. Check advice with your local KVK before spraying.</p>
    </section>
  );
}
