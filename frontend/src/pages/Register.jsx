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
  const navigate = useNavigate();
  const [form, setForm] = useState(EMPTY);
  const [errors, setErrors] = useState({});
  const [serverError, setServerError] = useState(null);
  const [busy, setBusy] = useState(false);

  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value });

  const submit = async (e) => {
    e.preventDefault();
    const found = validateRegistration(form);
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
        <ThemeSwitch onDark />
      </div>
      <div className="auth-page">
      <form className="auth-card auth-card-wide" onSubmit={submit} noValidate>
        <Link to="/" className="brand auth-brand">
          <Logo size={56} />
        </Link>
        <h1>Create your account</h1>
        <p className="muted">It takes a minute. Your mobile number is your login.</p>
        {serverError && (
          <div className="banner banner-error" role="alert">
            {serverError}
          </div>
        )}
        <div className="grid-2">
          <Field label="Full name" htmlFor="full_name" error={errors.full_name}>
            <input id="full_name" className="input" value={form.full_name} onChange={set("full_name")} autoComplete="name" />
          </Field>
          <Field label="Mobile number" htmlFor="phone" error={errors.phone}>
            <input id="phone" className="input" inputMode="tel" value={form.phone} onChange={set("phone")} autoComplete="tel" />
          </Field>
          <Field label="Email (optional)" htmlFor="email" error={errors.email}>
            <input id="email" type="email" className="input" value={form.email} onChange={set("email")} autoComplete="email" />
          </Field>
          <Field label="Preferred language" htmlFor="language" hint="Answers will be spoken in this language">
            <LanguageSelect value={form.preferred_language} onChange={(v) => setForm({ ...form, preferred_language: v })} />
          </Field>
          <Field label="Password" htmlFor="password" error={errors.password} hint="8+ characters, a letter and a number">
            <input id="password" type="password" className="input" value={form.password} onChange={set("password")} autoComplete="new-password" />
          </Field>
          <Field label="Confirm password" htmlFor="confirm" error={errors.confirm}>
            <input id="confirm" type="password" className="input" value={form.confirm} onChange={set("confirm")} autoComplete="new-password" />
          </Field>
          <Field label="State" htmlFor="state">
            <input id="state" className="input" value={form.state} onChange={set("state")} placeholder="Andhra Pradesh" />
          </Field>
          <Field label="District" htmlFor="district">
            <input id="district" className="input" value={form.district} onChange={set("district")} placeholder="Guntur" />
          </Field>
          <Field label="Village (optional)" htmlFor="village">
            <input id="village" className="input" value={form.village} onChange={set("village")} />
          </Field>
          <Field label="Main crops (optional)" htmlFor="crops" hint="Comma separated, e.g. paddy, chilli">
            <input id="crops" className="input" value={form.primary_crops} onChange={set("primary_crops")} />
          </Field>
        </div>
        <button className="btn btn-primary btn-block btn-large" disabled={busy}>
          {busy ? <Spinner label="Creating account…" /> : (<><UserPlus size={18} /> Register</>)}
        </button>
        <p className="auth-switch">
          Already registered? <Link to="/login">Log in</Link>
        </p>
      </form>
      </div>
    </div>
  );
}
