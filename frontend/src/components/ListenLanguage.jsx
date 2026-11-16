// Language picker for the text and voice of an explanation, plus a hook that translates
// English text into the chosen language (results are cached for this visit).
import { useEffect, useState } from "react";
import { Languages } from "lucide-react";
import { assistant } from "../api/endpoints";
import LanguageSelect from "./LanguageSelect";

export default function ListenLanguage({ value, onChange, id = "listen-lang" }) {
  return (
    <div className="field-inline listen-language">
      <label htmlFor={id}>
        <Languages size={16} aria-hidden /> Language
      </label>
      <LanguageSelect id={id} value={value} onChange={onChange} />
    </div>
  );
}

const cache = new Map();

/**
 * The text to show in `language`.
 * known: { [languageCode]: text } already available (e.g. the server's translation), used without a request.
 */
export function useTranslatedText(english, language, known = {}) {
  const ready = language === "en" ? english : known[language] ?? cache.get(`${language}|${english}`);
  const [state, setState] = useState({ text: ready ?? null, loading: ready == null, failed: false });
  useEffect(() => {
    if (!english) return undefined;
    if (ready != null) {
      setState({ text: ready, loading: false, failed: false });
      return undefined;
    }
    let alive = true;
    setState({ text: null, loading: true, failed: false });
    assistant
      .translate(english, language)
      .then((res) => {
        cache.set(`${language}|${english}`, res.text);
        if (alive) setState({ text: res.text, loading: false, failed: false });
      })
      .catch(() => alive && setState({ text: english, loading: false, failed: true }));
    return () => {
      alive = false;
    };
  }, [english, language, ready]);
  return state;
}

/** Speech props: speak the stored translation, or translate the English text into another language. */
export function speechSource(summary, summaryEnglish, summaryLanguage, listenLanguage) {
  if (!listenLanguage || listenLanguage === summaryLanguage) return { text: summary, translate: false };
  if (listenLanguage === "en") return { text: summaryEnglish, translate: false };
  return { text: summaryEnglish, translate: true };
}
