import { useEffect, useState } from "react";
import { meta } from "../api/endpoints";

let cache = null;

// Tested with real farmers' recordings: Telugu (20 questions), Hindi, Kannada, English. Others work
// end to end but have not been evaluated yet, so they are marked "beta".
export const TESTED_LANGUAGES = ["te", "hi", "kn", "ta", "gu", "en"];

export function languageLabel(l) {
  const base = l.native_name === l.name ? l.name : `${l.native_name} (${l.name})`;
  return TESTED_LANGUAGES.includes(l.code) ? base : `${base} · beta`;
}

/** Languages come from the backend `languages` table, so adding one there adds it here. */
export function useLanguages() {
  const [languages, setLanguages] = useState(cache || []);
  useEffect(() => {
    if (cache) return;
    meta
      .languages()
      .then((l) => {
        cache = l;
        setLanguages(l);
      })
      .catch(() => setLanguages([{ code: "en", name: "English", native_name: "English" }]));
  }, []);
  return languages;
}

export default function LanguageSelect({ value, onChange, id = "language", includeAuto = false, languages: given }) {
  const loaded = useLanguages();
  const languages = given || loaded;
  return (
    <select id={id} value={value} onChange={(e) => onChange(e.target.value)} className="select">
      {includeAuto && <option value="">Detect automatically</option>}
      {languages.map((l) => (
        <option key={l.code} value={l.code}>
          {languageLabel(l)}
        </option>
      ))}
    </select>
  );
}
