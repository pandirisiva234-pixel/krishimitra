// One audio player for the whole app. It lives in the page layout, so a spoken answer keeps
// playing while the farmer opens other pages. Long answers are played piece by piece: the first
// sentence starts quickly while the rest is still being turned into speech.
import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { assistant } from "../api/endpoints";

const SpeechContext = createContext(null);
const IDLE = { id: null, label: "", total: 0, index: 0, ready: 0, playing: false, failed: false };

export function SpeechProvider({ children }) {
  const audio = useRef(null);
  const urls = useRef([]); // object URLs of the pieces made so far
  const job = useRef(0); // increases on every new play/stop, so old downloads are ignored
  const [state, setState] = useState(IDLE);

  const release = () => {
    urls.current.forEach((u) => URL.revokeObjectURL(u));
    urls.current = [];
  };

  const stop = useCallback(() => {
    job.current += 1;
    audio.current?.pause();
    release();
    setState(IDLE);
  }, []);

  // translate=true: chunks are English and are translated into languageCode before speaking
  const play = useCallback(async (id, chunks, languageCode, label = "", translate = false) => {
    if (!chunks?.length) return;
    job.current += 1;
    const mine = job.current;
    audio.current?.pause();
    release();
    setState({ ...IDLE, id, label, total: chunks.length, playing: true });
    for (const text of chunks) {
      try {
        const out = await assistant.speak({ text, language_code: languageCode, translate_from_english: translate });
        const blob = await assistant.fetchBlob(out.audio_url);
        if (job.current !== mine) return; // stopped or replaced meanwhile
        urls.current.push(URL.createObjectURL(blob));
        setState((s) => ({ ...s, ready: urls.current.length }));
      } catch {
        if (job.current === mine) setState((s) => ({ ...s, failed: true, playing: s.ready > 0 && s.playing }));
        return;
      }
    }
  }, []);

  const toggle = useCallback(() => setState((s) => ({ ...s, playing: !s.playing })), []);

  // Play the current piece when it is ready; pause when asked
  useEffect(() => {
    const el = audio.current;
    if (!el || state.id === null) return;
    const src = urls.current[state.index];
    if (!state.playing) {
      el.pause();
      return;
    }
    if (!src) return; // still being made
    if (el.dataset.src !== src) {
      el.src = src;
      el.dataset.src = src;
    }
    el.play().catch(() => setState((s) => ({ ...s, playing: false })));
  }, [state.id, state.index, state.ready, state.playing]);

  const onEnded = () =>
    setState((s) => (s.index + 1 < s.total ? { ...s, index: s.index + 1 } : { ...s, index: 0, playing: false }));

  useEffect(() => () => release(), []);

  return (
    <SpeechContext.Provider value={{ ...state, play, toggle, stop }}>
      {children}
      <audio ref={audio} onEnded={onEnded} hidden />
    </SpeechContext.Provider>
  );
}

export function useSpeech() {
  const ctx = useContext(SpeechContext);
  if (!ctx) throw new Error("useSpeech must be used inside SpeechProvider");
  return ctx;
}
