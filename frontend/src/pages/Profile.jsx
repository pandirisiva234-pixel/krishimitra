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
import { useI18n } from "../i18n";

export default function Profile() {
  const { user, setUser } = useAuth();
  const { t, tm, setLang } = useI18n();
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
    if (!navigator.geolocation) return toast.error(t("profile.noGeo"));
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setForm((f) => ({ ...f, latitude: pos.coords.latitude.toFixed(4), longitude: pos.coords.longitude.toFixed(4) }));
        setLocating(false);
        toast.info(t("profile.locFound"));
      },
      () => {
        setLocating(false);
        toast.error(t("profile.locFailed"));
      },
      { enableHighAccuracy: true, timeout: 15000 },
    );
  };

  const save = async (e) => {
    e.preventDefault();
    const emailErr = validateEmail(form.email);
    if (emailErr) return toast.error(tm(emailErr));
    const lat = form.latitude === "" ? null : Number(form.latitude);
    const lon = form.longitude === "" ? null : Number(form.longitude);
    if ((lat === null) !== (lon === null)) return toast.error(t("profile.latLon"));
    setSaving(true);
    try {
      const body = { ...form, email: form.email || null, latitude: lat, longitude: lon };
      const saved = await auth.updateProfile(body);
      setUser(saved);
      setLang(saved.preferred_language?.code || form.preferred_language); // the app follows the saved language
      toast.success(t("profile.saved"));
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  const changePassword = async (e) => {
    e.preventDefault();
    const err = validatePassword(pw.new_password);
    if (err) return toast.error(`${t("profile.newPassword")}: ${tm(err)}`);
    if (pw.new_password !== pw.confirm) return toast.error(t("profile.noMatch"));
    setPwBusy(true);
    try {
      await auth.changePassword({ current_password: pw.current_password, new_password: pw.new_password });
      setPw({ current_password: "", new_password: "", confirm: "" });
      toast.success(t("profile.pwChanged"));
    } catch (e2) {
      toast.error(errorMessage(e2));
    } finally {
      setPwBusy(false);
    }
  };

  return (
    <div>
      <PageHeader title={t("profile.title")} subtitle={t("profile.subtitle", { phone: user.phone, date: formatDate(user.created_at) })} />
      <div className="grid-2">
        <Card title={t("profile.farmDetails")} icon={User}>
          <form onSubmit={save} className="form">
            <div className="grid-2">
              <Field label={t("form.fullName")} htmlFor="p-name">
                <input id="p-name" className="input" value={form.full_name} onChange={set("full_name")} />
              </Field>
              <Field label={t("form.email")} htmlFor="p-email">
                <input id="p-email" className="input" type="email" value={form.email} onChange={set("email")} />
              </Field>
              <Field label={t("form.language")} htmlFor="p-lang" hint={t("profile.langHint")}>
                <LanguageSelect id="p-lang" value={form.preferred_language} onChange={(v) => setForm({ ...form, preferred_language: v })} />
              </Field>
              <Field label={t("form.crops")} htmlFor="p-crops" hint={t("profile.cropsHint")}>
                <input id="p-crops" className="input" value={form.primary_crops} onChange={set("primary_crops")} />
              </Field>
              <Field label={t("form.state")} htmlFor="p-state">
                <input id="p-state" className="input" value={form.state} onChange={set("state")} />
              </Field>
              <Field label={t("form.district")} htmlFor="p-district">
                <input id="p-district" className="input" value={form.district} onChange={set("district")} />
              </Field>
              <Field label={t("form.village")} htmlFor="p-village">
                <input id="p-village" className="input" value={form.village} onChange={set("village")} />
              </Field>
              <div />
              <Field label={t("profile.latitude")} htmlFor="p-lat">
                <input id="p-lat" className="input" inputMode="decimal" value={form.latitude} onChange={set("latitude")} />
              </Field>
              <Field label={t("profile.longitude")} htmlFor="p-lon">
                <input id="p-lon" className="input" inputMode="decimal" value={form.longitude} onChange={set("longitude")} />
              </Field>
            </div>
            <div className="row">
              <button type="button" className="btn btn-ghost" onClick={locate} disabled={locating}>
                {locating ? <Spinner label={t("profile.locating")} size={16} /> : (<><LocateFixed size={18} /> {t("common.useLocation")}</>)}
              </button>
              <button className="btn btn-primary" disabled={saving}>
                {saving ? <Spinner label={t("common.saving")} size={16} /> : (<><Save size={18} /> {t("profile.save")}</>)}
              </button>
            </div>
          </form>
        </Card>

        <Card title={t("profile.changePassword")} icon={KeyRound}>
          <form onSubmit={changePassword} className="form">
            <Field label={t("profile.currentPassword")} htmlFor="pw-cur">
              <input id="pw-cur" type="password" className="input" autoComplete="current-password"
                value={pw.current_password} onChange={(e) => setPw({ ...pw, current_password: e.target.value })} />
            </Field>
            <Field label={t("profile.newPassword")} htmlFor="pw-new" hint={t("form.passwordHint")}>
              <input id="pw-new" type="password" className="input" autoComplete="new-password"
                value={pw.new_password} onChange={(e) => setPw({ ...pw, new_password: e.target.value })} />
            </Field>
            <Field label={t("profile.confirmNew")} htmlFor="pw-confirm">
              <input id="pw-confirm" type="password" className="input" autoComplete="new-password"
                value={pw.confirm} onChange={(e) => setPw({ ...pw, confirm: e.target.value })} />
            </Field>
            <button className="btn btn-primary" disabled={pwBusy || !pw.current_password}>
              {pwBusy ? <Spinner label={t("common.saving")} size={16} /> : t("profile.changePassword")}
            </button>
          </form>
        </Card>
      </div>
    </div>
  );
}
