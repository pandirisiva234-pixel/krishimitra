import { useEffect, useState } from "react";
import { meta } from "../api/endpoints";
import { useI18n } from "../i18n";

let cache = null;

// Languages with a language-specific speech model (IIT Madras) that were tested end to end.
// The others work end to end with the general Whisper model and are marked "beta".
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
  const { t } = useI18n();
  const loaded = useLanguages();
  const languages = given || loaded;
  return (
    <select id={id} value={value} onChange={(e) => onChange(e.target.value)} className="select">
      {includeAuto && <option value="">{t("lang.auto")}</option>}
      {languages.map((l) => (
        <option key={l.code} value={l.code}>
          {languageLabel(l)}
        </option>
      ))}
    </select>
  );
}
