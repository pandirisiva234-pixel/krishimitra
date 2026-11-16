// Small player shown on every page while an answer is being spoken.
import { Link, useLocation } from "react-router-dom";
import { Pause, Play, Square, Volume2 } from "lucide-react";
import { useSpeech } from "../context/SpeechContext";

export default function NowPlaying() {
  const speech = useSpeech();
  const { pathname } = useLocation();
  if (speech.id === null) return null;
  return (
    <div className="now-playing" role="region" aria-label="Spoken answer">
      <Volume2 size={18} aria-hidden className="now-playing-icon" />
      <div className="now-playing-text">
        <strong>{speech.playing ? "Speaking the answer" : "Answer paused"}</strong>
        <span className="small">
          Part {Math.min(speech.index + 1, speech.total)} of {speech.total}
          {speech.label ? ` · ${speech.label}` : ""}
        </span>
      </div>
      <button className="icon-btn" onClick={speech.toggle} aria-label={speech.playing ? "Pause" : "Play"}>
        {speech.playing ? <Pause size={18} /> : <Play size={18} />}
      </button>
      <button className="icon-btn" onClick={speech.stop} aria-label="Stop">
        <Square size={16} />
      </button>
      {pathname !== "/assistant" && speech.id?.startsWith?.("answer-") && (
        <Link to="/assistant" className="now-playing-link">Open chat</Link>
      )}
    </div>
  );
}
