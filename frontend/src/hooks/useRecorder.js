import { useCallback, useEffect, useRef, useState } from "react";

const MAX_SECONDS = 60;

function pickMimeType() {
  if (typeof MediaRecorder === "undefined") return null;
  const options = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg;codecs=opus"];
  return options.find((t) => MediaRecorder.isTypeSupported(t)) || "";
}

function extensionFor(mime) {
  if (mime.includes("mp4")) return ".m4a";
  if (mime.includes("ogg")) return ".ogg";
  return ".webm";
}

/**
 * Microphone recording with MediaRecorder.
 * Returns { state, seconds, level, error, start, stop, reset, result } where
 * result = { blob, filename, url } after stopping.
 * Browsers only allow the microphone on https:// or http://localhost.
 */
export default function useRecorder() {
  const [state, setState] = useState("idle"); // idle | recording | done
  const [seconds, setSeconds] = useState(0);
  const [level, setLevel] = useState(0);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const refs = useRef({});

  const cleanup = useCallback(() => {
    const r = refs.current;
    clearInterval(r.timer);
    cancelAnimationFrame(r.raf);
    r.stream?.getTracks().forEach((t) => t.stop());
    r.audioCtx?.close().catch(() => {});
    refs.current = {};
  }, []);

  useEffect(() => cleanup, [cleanup]);

  const stop = useCallback(() => {
    const rec = refs.current.recorder;
    if (rec && rec.state !== "inactive") rec.stop();
  }, []);

  const start = useCallback(async () => {
    setError(null);
    setResult(null);
    const mime = pickMimeType();
    if (mime === null || !navigator.mediaDevices?.getUserMedia) {
      setError("This browser cannot record audio. Use Chrome, Edge or Firefox, or type your question.");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, channelCount: 1 },
      });
      const recorder = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
      const chunks = [];
      recorder.ondataavailable = (e) => e.data.size && chunks.push(e.data);
      recorder.onstop = () => {
        const type = recorder.mimeType || mime || "audio/webm";
        const blob = new Blob(chunks, { type });
        setResult({ blob, filename: `question${extensionFor(type)}`, url: URL.createObjectURL(blob) });
        setState("done");
        cleanup();
      };

      // Live input level so the farmer can see the mic is hearing them
      const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = 256;
      audioCtx.createMediaStreamSource(stream).connect(analyser);
      const buf = new Uint8Array(analyser.frequencyBinCount);
      const tick = () => {
        analyser.getByteTimeDomainData(buf);
        let peak = 0;
        for (const v of buf) peak = Math.max(peak, Math.abs(v - 128));
        setLevel(Math.min(1, peak / 64));
        refs.current.raf = requestAnimationFrame(tick);
      };

      refs.current = { stream, recorder, audioCtx };
      recorder.start();
      tick();
      setSeconds(0);
      setState("recording");
      const started = Date.now();
      refs.current.timer = setInterval(() => {
        const s = Math.floor((Date.now() - started) / 1000);
        setSeconds(s);
        if (s >= MAX_SECONDS) recorder.stop();
      }, 250);
    } catch (e) {
      cleanup();
      setError(
        e?.name === "NotAllowedError"
          ? "Microphone permission was denied. Allow it in the browser address bar and try again."
          : "Could not start the microphone. Check that one is connected.",
      );
    }
  }, [cleanup]);

  const reset = useCallback(() => {
    if (result?.url) URL.revokeObjectURL(result.url);
    setResult(null);
    setSeconds(0);
    setState("idle");
  }, [result]);

  return { state, seconds, level, error, start, stop, reset, result, maxSeconds: MAX_SECONDS };
}
