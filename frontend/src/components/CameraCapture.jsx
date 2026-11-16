import { useEffect, useRef, useState } from "react";
import { Camera, X } from "lucide-react";

/** Live camera preview; "Capture" returns a JPEG Blob via onCapture. Uses the back camera on phones. */
export default function CameraCapture({ onCapture, onClose }) {
  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const [error, setError] = useState(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    if (!navigator.mediaDevices?.getUserMedia) {
      setError("This browser cannot open the camera. Upload a photo instead.");
      return undefined;
    }
    navigator.mediaDevices
      .getUserMedia({ video: { facingMode: { ideal: "environment" }, width: { ideal: 1280 } }, audio: false })
      .then((stream) => {
        if (cancelled) return stream.getTracks().forEach((t) => t.stop());
        streamRef.current = stream;
        videoRef.current.srcObject = stream;
        videoRef.current.onloadedmetadata = () => setReady(true);
      })
      .catch((e) =>
        setError(e?.name === "NotAllowedError" ? "Camera permission was denied." : "No camera found. Upload a photo instead."),
      );
    return () => {
      cancelled = true;
      streamRef.current?.getTracks().forEach((t) => t.stop());
    };
  }, []);

  const capture = () => {
    const video = videoRef.current;
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext("2d").drawImage(video, 0, 0);
    canvas.toBlob((blob) => blob && onCapture(blob), "image/jpeg", 0.92);
  };

  return (
    <div className="camera">
      {error ? (
        <p className="banner banner-error">{error}</p>
      ) : (
        <>
          <video ref={videoRef} autoPlay playsInline muted className="camera-video" />
          <div className="camera-guide" aria-hidden>
            Fill the frame with one leaf
          </div>
        </>
      )}
      <div className="camera-actions">
        <button className="btn btn-ghost" onClick={onClose}>
          <X size={18} /> Close
        </button>
        {!error && (
          <button className="btn btn-primary" onClick={capture} disabled={!ready}>
            <Camera size={18} /> Capture
          </button>
        )}
      </div>
    </div>
  );
}
