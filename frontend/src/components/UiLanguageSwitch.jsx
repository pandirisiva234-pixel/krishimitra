import { useEffect } from "react";
import { Globe } from "lucide-react";
import { UI_LANGUAGES, isUiLanguage, useI18n } from "../i18n";
import { useAuth } from "../context/AuthContext";

/** Interface language picker shown in the top bar of every page. */
export default function UiLanguageSwitch({ onDark = false }) {
  const { lang, setLang, t } = useI18n();
  return (
    <label className={`ui-lang ${onDark ? "on-dark" : ""}`} title={t("ui.language")}>
      <Globe size={16} aria-hidden />
      <span className="sr-only">{t("ui.language")}</span>
      <select value={lang} onChange={(e) => setLang(e.target.value)} aria-label={t("ui.language")}>
        {UI_LANGUAGES.map((l) => (
          <option key={l.code} value={l.code}>
            {l.native}
          </option>
        ))}
      </select>
    </label>
  );
}

/** Until the farmer picks a language here, the interface follows the language saved in their profile. */
export function FollowProfileLanguage() {
  const { user } = useAuth();
  const { chosen, setLang } = useI18n();
  const code = user?.preferred_language?.code;
  useEffect(() => {
    if (!chosen && isUiLanguage(code)) setLang(code, { remember: false });
  }, [chosen, code, setLang]);
  return null;
}
