// Weather advisories come from the server in English; they are shown in the interface language
// using the same translation service as disease advice (one request for the whole list).
import { useI18n } from "../i18n";
import { useTranslatedText } from "./ListenLanguage";
import { Spinner } from "./ui";

export default function AdvisoryList({ advisories }) {
  const { lang, t } = useI18n();
  const english = advisories.flatMap((a) => [a.title, a.message]).join("\n");
  const translated = useTranslatedText(lang === "en" ? "" : english, lang);
  if (!advisories.length) return null;
  if (lang !== "en" && translated.loading) return <Spinner label={t("common.translating")} size={16} />;
  const lines = lang !== "en" && translated.text ? translated.text.split("\n") : null;
  const usable = lines && lines.length === advisories.length * 2;
  return (
    <ul className="advisory-list">
      {advisories.map((a, i) => (
        <li key={a.title} className={`advisory advisory-${a.level}`}>
          <strong>{usable ? lines[i * 2] : a.title}</strong>
          <span>{usable ? lines[i * 2 + 1] : a.message}</span>
        </li>
      ))}
    </ul>
  );
}
