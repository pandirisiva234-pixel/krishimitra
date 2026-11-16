import { useEffect, useState } from "react";
import { Laptop, Moon, Sun } from "lucide-react";
import { applyTheme, savedTheme } from "../context/theme";

const OPTIONS = [
  { value: "light", label: "Light mode", icon: Sun },
  { value: "dark", label: "Dark mode", icon: Moon },
  { value: "system", label: "Use device setting", icon: Laptop },
];

export default function ThemeSwitch({ onDark = false }) {
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
    <div className={`theme-switch ${onDark ? "on-dark" : ""}`} role="group" aria-label="Colour theme">
      {OPTIONS.map(({ value, label, icon: Icon }) => (
        <button key={value} type="button" title={label} aria-label={label} aria-pressed={choice === value}
          onClick={() => setChoice(value)}>
          <Icon size={16} />
        </button>
      ))}
    </div>
  );
}
