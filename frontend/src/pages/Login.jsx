import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { LogIn } from "lucide-react";
import { errorMessage } from "../api/client";
import { Field, Spinner } from "../components/ui";
import { useAuth } from "../context/AuthContext";
import Logo from "../components/Logo";
import ThemeSwitch from "../components/ThemeSwitch";
import { useI18n } from "../i18n";
import UiLanguageSwitch from "../components/UiLanguageSwitch";

export default function Login() {
  const { login } = useAuth();
  const { t } = useI18n();
  const navigate = useNavigate();
  const location = useLocation();
  const [form, setForm] = useState({ username: "", password: "" });
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    if (!form.username.trim() || !form.password) {
      setError(t("login.missing"));
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const user = await login(form.username.trim(), form.password);
      navigate(location.state?.from || (user.role === "admin" ? "/admin" : "/dashboard"), { replace: true });
    } catch (err) {
      setError(errorMessage(err));
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
      <form className="auth-card" onSubmit={submit} noValidate>
        <Link to="/" className="brand auth-brand">
          <Logo size={56} />
        </Link>
        <h1>{t("login.title")}</h1>
        <p className="muted">{t("login.subtitle")}</p>
        {error && (
          <div className="banner banner-error" role="alert">
            {error}
          </div>
        )}
        <Field label={t("login.username")} htmlFor="username">
          <input
            id="username"
            className="input"
            autoComplete="username"
            inputMode="tel"
            value={form.username}
            onChange={(e) => setForm({ ...form, username: e.target.value })}
            placeholder="98765 43210"
          />
        </Field>
        <Field label={t("form.password")} htmlFor="password">
          <input
            id="password"
            type="password"
            className="input"
            autoComplete="current-password"
            value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })}
          />
        </Field>
        <button className="btn btn-primary btn-block btn-large" disabled={busy}>
          {busy ? <Spinner label={t("login.busy")} /> : (<><LogIn size={18} /> {t("login.button")}</>)}
        </button>
        <p className="auth-switch">
          {t("login.newHere")} <Link to="/register">{t("login.create")}</Link>
        </p>
      </form>
      </div>
    </div>
  );
}
