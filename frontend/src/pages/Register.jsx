import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { UserPlus } from "lucide-react";
import { errorMessage } from "../api/client";
import LanguageSelect from "../components/LanguageSelect";
import { Field, Spinner } from "../components/ui";
import { useAuth } from "../context/AuthContext";
import Logo from "../components/Logo";
import ThemeSwitch from "../components/ThemeSwitch";
import { normalisePhone, validateRegistration } from "../utils/validation";
import { useI18n } from "../i18n";
import UiLanguageSwitch from "../components/UiLanguageSwitch";

const EMPTY = {
  full_name: "",
  phone: "",
  email: "",
  password: "",
  confirm: "",
  preferred_language: "te",
  state: "",
  district: "",
  village: "",
  primary_crops: "",
};

export default function Register() {
  const { register } = useAuth();
  const { t, tm, lang } = useI18n();
  const navigate = useNavigate();
  const [form, setForm] = useState({ ...EMPTY, preferred_language: lang === "en" ? EMPTY.preferred_language : lang });
  const [errors, setErrors] = useState({});
  const [serverError, setServerError] = useState(null);
  const [busy, setBusy] = useState(false);

  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value });

  const submit = async (e) => {
    e.preventDefault();
    const found = Object.fromEntries(Object.entries(validateRegistration(form)).map(([k, v]) => [k, tm(v)]));
    setErrors(found);
    if (Object.keys(found).length) return;
    setBusy(true);
    setServerError(null);
    const { confirm, ...body } = form;
    const payload = Object.fromEntries(
      Object.entries({ ...body, phone: normalisePhone(body.phone) }).filter(([, v]) => v !== ""),
    );
    try {
      await register(payload);
      navigate("/dashboard", { replace: true });
    } catch (err) {
      setServerError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="auth-shell">
      <div className="auth-topbar-row">
        <Link to="/" className="auth-topbar">
          <Logo size={30} tagline={null} tone="light" />
        </Link>
        <span className="row-tight"><UiLanguageSwitch onDark /><ThemeSwitch onDark /></span>
      </div>
      <div className="auth-page">
      <form className="auth-card auth-card-wide" onSubmit={submit} noValidate>
        <Link to="/" className="brand auth-brand">
          <Logo size={56} />
        </Link>
        <h1>{t("register.title")}</h1>
        <p className="muted">{t("register.subtitle")}</p>
        {serverError && (
          <div className="banner banner-error" role="alert">
            {serverError}
          </div>
        )}
        <div className="grid-2">
          <Field label={t("form.fullName")} htmlFor="full_name" error={errors.full_name}>
            <input id="full_name" className="input" value={form.full_name} onChange={set("full_name")} autoComplete="name" />
          </Field>
          <Field label={t("form.mobile")} htmlFor="phone" error={errors.phone}>
            <input id="phone" className="input" inputMode="tel" value={form.phone} onChange={set("phone")} autoComplete="tel" />
          </Field>
          <Field label={t("form.emailOptional")} htmlFor="email" error={errors.email}>
            <input id="email" type="email" className="input" value={form.email} onChange={set("email")} autoComplete="email" />
          </Field>
          <Field label={t("form.language")} htmlFor="language" hint={t("register.langHint")}>
            <LanguageSelect value={form.preferred_language} onChange={(v) => setForm({ ...form, preferred_language: v })} />
          </Field>
          <Field label={t("form.password")} htmlFor="password" error={errors.password} hint={t("form.passwordHint")}>
            <input id="password" type="password" className="input" value={form.password} onChange={set("password")} autoComplete="new-password" />
          </Field>
          <Field label={t("form.confirmPassword")} htmlFor="confirm" error={errors.confirm}>
            <input id="confirm" type="password" className="input" value={form.confirm} onChange={set("confirm")} autoComplete="new-password" />
          </Field>
          <Field label={t("form.state")} htmlFor="state">
            <input id="state" className="input" value={form.state} onChange={set("state")} placeholder="Andhra Pradesh" />
          </Field>
          <Field label={t("form.district")} htmlFor="district">
            <input id="district" className="input" value={form.district} onChange={set("district")} placeholder="Guntur" />
          </Field>
          <Field label={t("form.villageOptional")} htmlFor="village">
            <input id="village" className="input" value={form.village} onChange={set("village")} />
          </Field>
          <Field label={t("form.cropsOptional")} htmlFor="crops" hint={t("register.cropsHint")}>
            <input id="crops" className="input" value={form.primary_crops} onChange={set("primary_crops")} />
          </Field>
        </div>
        <button className="btn btn-primary btn-block btn-large" disabled={busy}>
          {busy ? <Spinner label={t("register.busy")} /> : (<><UserPlus size={18} /> {t("register.button")}</>)}
        </button>
        <p className="auth-switch">
          {t("register.already")} <Link to="/login">{t("login.button")}</Link>
        </p>
      </form>
      </div>
    </div>
  );
}
