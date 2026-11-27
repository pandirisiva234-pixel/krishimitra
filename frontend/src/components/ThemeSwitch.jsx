import { useEffect, useState } from "react";
import { Laptop, Moon, Sun } from "lucide-react";
import { applyTheme, savedTheme } from "../context/theme";
import { useI18n } from "../i18n";

const OPTIONS = [
  { value: "light", label: "theme.light", icon: Sun },
  { value: "dark", label: "theme.dark", icon: Moon },
  { value: "system", label: "theme.system", icon: Laptop },
];

export default function ThemeSwitch({ onDark = false }) {
  const { t } = useI18n();
  const [choice, setChoice] = useState(savedTheme);

  useEffect(() => {
    applyTheme(choice);
    if (choice !== "system" || !window.matchMedia) return undefined;
    // follow the device when it switches between light and dark
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => applyTheme("system");
    media.addEventListener?.("change", onChange);
    return () => media.removeEventListener?.("change", onChange);
  }, [choice]);

  return (
    <div className={`theme-switch ${onDark ? "on-dark" : ""}`} role="group" aria-label={t("theme.label")}>
      {OPTIONS.map(({ value, label, icon: Icon }) => (
        <button key={value} type="button" title={t(label)} aria-label={t(label)} aria-pressed={choice === value}
          onClick={() => setChoice(value)}>
          <Icon size={16} />
        </button>
      ))}
    </div>
  );
}
