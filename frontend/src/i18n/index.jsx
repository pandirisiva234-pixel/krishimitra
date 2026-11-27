// App-wide interface language. Every farmer-facing label is looked up with t("key"); the farmer's
// choice is remembered in this browser, and the first choice follows the language in the profile.
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { MESSAGE_KEYS, STRINGS } from "./strings";

export const UI_LANGUAGES = [
  { code: "en", native: "English" },
  { code: "te", native: "తెలుగు" },
  { code: "hi", native: "हिन्दी" },
  { code: "kn", native: "ಕನ್ನಡ" },
  { code: "ta", native: "தமிழ்" },
  { code: "ml", native: "മലയാളം" },
  { code: "mr", native: "मराठी" },
  { code: "bn", native: "বাংলা" },
  { code: "gu", native: "ગુજરાતી" },
  { code: "ur", native: "اردو" },
];
const CODES = new Set(UI_LANGUAGES.map((l) => l.code));
const STORAGE_KEY = "krishimitra_ui_language";

let current = "en";

function stored() {
  try {
    const v = localStorage.getItem(STORAGE_KEY);
    return CODES.has(v) ? v : null;
  } catch {
    return null;
  }
}

/** Text for `key` in the current language ({name} placeholders filled from vars); English if missing. */
export function translate(key, vars, lang = current) {
  let text = STRINGS[lang]?.[key] ?? STRINGS.en[key] ?? key;
  if (vars) for (const [k, v] of Object.entries(vars)) text = text.replaceAll(`{${k}}`, String(v));
  return text;
}

/** Fixed English messages made outside React (form checks, microphone errors) in the current language. */
export function translateMessage(message, lang = current) {
  const key = MESSAGE_KEYS[message];
  return key ? translate(key, null, lang) : message;
}

const I18nContext = createContext({
  lang: "en",
  setLang: () => {},
  t: (k, v) => translate(k, v),
  tm: (m) => translateMessage(m),
  chosen: false,
});

export function I18nProvider({ children }) {
  const [lang, setLangState] = useState(() => stored() || "en");
  const [chosen, setChosen] = useState(() => stored() !== null);
  current = lang;

  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  const setLang = useCallback((code, { remember = true } = {}) => {
    if (!CODES.has(code)) return;
    current = code;
    setLangState(code);
    if (remember) {
      setChosen(true);
      try {
        localStorage.setItem(STORAGE_KEY, code);
      } catch {
        /* storage unavailable: the choice lasts until the page is closed */
      }
    }
  }, []);

  const value = useMemo(() => ({ lang, setLang, chosen, t: (k, v) => translate(k, v, lang), tm: (m) => translateMessage(m, lang) }), [lang, setLang, chosen]);
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n() {
  return useContext(I18nContext);
}

export function isUiLanguage(code) {
  return CODES.has(code);
}
