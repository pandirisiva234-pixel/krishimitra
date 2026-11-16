import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { LogIn } from "lucide-react";
import { errorMessage } from "../api/client";
import { Field, Spinner } from "../components/ui";
import { useAuth } from "../context/AuthContext";
import Logo from "../components/Logo";
import ThemeSwitch from "../components/ThemeSwitch";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [form, setForm] = useState({ username: "", password: "" });
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    if (!form.username.trim() || !form.password) {
      setError("Enter your mobile number (or email) and password");
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
        <ThemeSwitch onDark />
      </div>
      <div className="auth-page">
      <form className="auth-card" onSubmit={submit} noValidate>
        <Link to="/" className="brand auth-brand">
          <Logo size={56} />
        </Link>
        <h1>Welcome back</h1>
        <p className="muted">Log in to ask questions and check your crops.</p>
        {error && (
          <div className="banner banner-error" role="alert">
            {error}
          </div>
        )}
        <Field label="Mobile number or email" htmlFor="username">
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
        <Field label="Password" htmlFor="password">
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
          {busy ? <Spinner label="Logging in…" /> : (<><LogIn size={18} /> Log in</>)}
        </button>
        <p className="auth-switch">
          New here? <Link to="/register">Create an account</Link>
        </p>
      </form>
      </div>
    </div>
  );
}
