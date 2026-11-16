import { useState } from "react";
import { KeyRound, LocateFixed, Save, User } from "lucide-react";
import { errorMessage } from "../api/client";
import { auth } from "../api/endpoints";
import LanguageSelect from "../components/LanguageSelect";
import { Card, Field, PageHeader, Spinner } from "../components/ui";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import { formatDate } from "../utils/format";
import { validateEmail, validatePassword } from "../utils/validation";

export default function Profile() {
  const { user, setUser } = useAuth();
  const toast = useToast();
  const [form, setForm] = useState({
    full_name: user.full_name,
    email: user.email || "",
    preferred_language: user.preferred_language.code,
    state: user.state || "",
    district: user.district || "",
    village: user.village || "",
    primary_crops: user.primary_crops || "",
    latitude: user.latitude ?? "",
    longitude: user.longitude ?? "",
  });
  const [saving, setSaving] = useState(false);
  const [locating, setLocating] = useState(false);
  const [pw, setPw] = useState({ current_password: "", new_password: "", confirm: "" });
  const [pwBusy, setPwBusy] = useState(false);

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const locate = () => {
    if (!navigator.geolocation) return toast.error("Location is not available in this browser.");
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setForm((f) => ({ ...f, latitude: pos.coords.latitude.toFixed(4), longitude: pos.coords.longitude.toFixed(4) }));
        setLocating(false);
        toast.info("Location found. Remember to save.");
      },
      () => {
        setLocating(false);
        toast.error("Could not get your location. Allow location access or type it in.");
      },
      { enableHighAccuracy: true, timeout: 15000 },
    );
  };

  const save = async (e) => {
    e.preventDefault();
    const emailErr = validateEmail(form.email);
    if (emailErr) return toast.error(emailErr);
    const lat = form.latitude === "" ? null : Number(form.latitude);
    const lon = form.longitude === "" ? null : Number(form.longitude);
    if ((lat === null) !== (lon === null)) return toast.error("Enter both latitude and longitude, or neither.");
    setSaving(true);
    try {
      const body = { ...form, email: form.email || null, latitude: lat, longitude: lon };
      setUser(await auth.updateProfile(body));
      toast.success("Profile saved");
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  const changePassword = async (e) => {
    e.preventDefault();
    const err = validatePassword(pw.new_password);
    if (err) return toast.error(`New password: ${err}`);
    if (pw.new_password !== pw.confirm) return toast.error("New passwords do not match");
    setPwBusy(true);
    try {
      await auth.changePassword({ current_password: pw.current_password, new_password: pw.new_password });
      setPw({ current_password: "", new_password: "", confirm: "" });
      toast.success("Password changed");
    } catch (e2) {
      toast.error(errorMessage(e2));
    } finally {
      setPwBusy(false);
    }
  };

  return (
    <div>
      <PageHeader title="Your profile" subtitle={`Mobile ${user.phone} · member since ${formatDate(user.created_at)}`} />
      <div className="grid-2">
        <Card title="Farm details" icon={User}>
          <form onSubmit={save} className="form">
            <div className="grid-2">
              <Field label="Full name" htmlFor="p-name">
                <input id="p-name" className="input" value={form.full_name} onChange={set("full_name")} />
              </Field>
              <Field label="Email" htmlFor="p-email">
                <input id="p-email" className="input" type="email" value={form.email} onChange={set("email")} />
              </Field>
              <Field label="Preferred language" htmlFor="p-lang" hint="Used for spoken answers">
                <LanguageSelect id="p-lang" value={form.preferred_language} onChange={(v) => setForm({ ...form, preferred_language: v })} />
              </Field>
              <Field label="Main crops" htmlFor="p-crops" hint="Helps tailor answers">
                <input id="p-crops" className="input" value={form.primary_crops} onChange={set("primary_crops")} />
              </Field>
              <Field label="State" htmlFor="p-state">
                <input id="p-state" className="input" value={form.state} onChange={set("state")} />
              </Field>
              <Field label="District" htmlFor="p-district">
                <input id="p-district" className="input" value={form.district} onChange={set("district")} />
              </Field>
              <Field label="Village" htmlFor="p-village">
                <input id="p-village" className="input" value={form.village} onChange={set("village")} />
              </Field>
              <div />
              <Field label="Latitude" htmlFor="p-lat">
                <input id="p-lat" className="input" inputMode="decimal" value={form.latitude} onChange={set("latitude")} />
              </Field>
              <Field label="Longitude" htmlFor="p-lon">
                <input id="p-lon" className="input" inputMode="decimal" value={form.longitude} onChange={set("longitude")} />
              </Field>
            </div>
            <div className="row">
              <button type="button" className="btn btn-ghost" onClick={locate} disabled={locating}>
                {locating ? <Spinner label="Locating…" size={16} /> : (<><LocateFixed size={18} /> Use my current location</>)}
              </button>
              <button className="btn btn-primary" disabled={saving}>
                {saving ? <Spinner label="Saving…" size={16} /> : (<><Save size={18} /> Save profile</>)}
              </button>
            </div>
          </form>
        </Card>

        <Card title="Change password" icon={KeyRound}>
          <form onSubmit={changePassword} className="form">
            <Field label="Current password" htmlFor="pw-cur">
              <input id="pw-cur" type="password" className="input" autoComplete="current-password"
                value={pw.current_password} onChange={(e) => setPw({ ...pw, current_password: e.target.value })} />
            </Field>
            <Field label="New password" htmlFor="pw-new" hint="8+ characters, a letter and a number">
              <input id="pw-new" type="password" className="input" autoComplete="new-password"
                value={pw.new_password} onChange={(e) => setPw({ ...pw, new_password: e.target.value })} />
            </Field>
            <Field label="Confirm new password" htmlFor="pw-confirm">
              <input id="pw-confirm" type="password" className="input" autoComplete="new-password"
                value={pw.confirm} onChange={(e) => setPw({ ...pw, confirm: e.target.value })} />
            </Field>
            <button className="btn btn-primary" disabled={pwBusy || !pw.current_password}>
              {pwBusy ? <Spinner label="Changing…" size={16} /> : "Change password"}
            </button>
          </form>
        </Card>
      </div>
    </div>
  );
}
