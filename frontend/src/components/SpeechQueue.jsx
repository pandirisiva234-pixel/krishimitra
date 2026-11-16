// Listen / Pause button for one answer. Playback itself is done by the app-wide player
// (SpeechContext), so it continues when the farmer moves to another page.
import { useEffect, useRef } from "react";
import { Pause, Play, Square, Volume2 } from "lucide-react";
import { useSpeech } from "../context/SpeechContext";
import { Spinner } from "./ui";

export default function SpeechQueue({ id, chunks, languageCode, autoPlay = false, label = "", translate = false }) {
  const speech = useSpeech();
  const started = useRef(false);
  const current = speech.id === id;

  useEffect(() => {
    if (autoPlay && !started.current && !current && chunks?.length) {
      started.current = true;
      speech.play(id, chunks, languageCode, label, translate);
    }
  }, [autoPlay]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!chunks?.length) return null;
  if (!current) {
    return (
      <div className="speech-queue">
        <button className="btn btn-ghost btn-small" onClick={() => speech.play(id, chunks, languageCode, label, translate)}>
          <Play size={16} /> Listen
        </button>
      </div>
    );
  }
  const waiting = speech.playing && speech.ready <= speech.index && !speech.failed;
  return (
    <div className="speech-queue">
      <button className="btn btn-ghost btn-small" onClick={speech.toggle} disabled={speech.ready === 0 && !speech.failed}>
        {speech.playing ? <Pause size={16} /> : <Play size={16} />} {speech.playing ? "Pause" : "Listen"}
      </button>
      <button className="btn btn-ghost btn-small" onClick={speech.stop} aria-label="Stop">
        <Square size={14} /> Stop
      </button>
      <span className="muted small">
        <Volume2 size={14} aria-hidden /> Part {Math.min(speech.index + 1, speech.total)} of {speech.total}
      </span>
      {waiting && <Spinner label="Preparing audio…" size={14} />}
      {speech.failed && speech.ready === 0 && <span className="muted small">Audio unavailable</span>}
    </div>
  );
}
