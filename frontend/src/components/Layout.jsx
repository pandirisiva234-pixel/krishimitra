import { useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import {
  BookOpen,
  CloudSun,
  FileText,
  HelpCircle,
  History,
  LayoutDashboard,
  Leaf,
  LogOut,
  Menu,
  Mic,
  PackageSearch,
  Shield,
  User,
  Sprout,
  Users,
  X,
} from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { SpeechProvider } from "../context/SpeechContext";
import Logo from "./Logo";
import NowPlaying from "./NowPlaying";
import ThemeSwitch from "./ThemeSwitch";
import { useI18n } from "../i18n";
import UiLanguageSwitch, { FollowProfileLanguage } from "./UiLanguageSwitch";
import UserGuide, { guideSeen, markGuideSeen } from "./UserGuide";

const FARMER_LINKS = [
  { to: "/dashboard", label: "nav.dashboard", icon: LayoutDashboard },
  { to: "/assistant", label: "nav.assistant", icon: Mic },
  { to: "/disease", label: "nav.disease", icon: Leaf },
  { to: "/items", label: "nav.items", icon: PackageSearch },
  { to: "/weather", label: "nav.weather", icon: CloudSun },
  { to: "/knowledge", label: "nav.knowledge", icon: BookOpen },
  { to: "/history", label: "nav.history", icon: History },
  { to: "/profile", label: "nav.profile", icon: User },
];

const ADMIN_LINKS = [
  { to: "/admin", label: "nav.admin", icon: Shield, end: true },
  { to: "/admin/users", label: "nav.users", icon: Users },
  { to: "/admin/documents", label: "nav.documents", icon: FileText },
];

export default function Layout() {
  const { user, isAdmin, logout } = useAuth();
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const [guide, setGuide] = useState(() => !isAdmin && !guideSeen());
  const closeGuide = () => {
    markGuideSeen();
    setGuide(false);
  };
  const navigate = useNavigate();

  const links = (items) =>
    items.map(({ to, label, icon: Icon, end }) => (
      <NavLink key={to} to={to} end={end} className="nav-link" onClick={() => setOpen(false)}>
        <Icon size={18} aria-hidden /> <span>{t(label)}</span>
      </NavLink>
    ));

  return (
    <SpeechProvider>
    <div className="app-shell">
      <aside className={`sidebar ${open ? "open" : ""}`}>
        <div className="brand">
          <Logo size={42} tone="light" />
          <button className="icon-btn sidebar-close" onClick={() => setOpen(false)} aria-label={t("nav.closeMenu")}>
            <X size={20} />
          </button>
        </div>
        <div className="workspace-card">
          <div>
            <div className="workspace-kicker">{isAdmin ? t("nav.adminWorkspace") : t("nav.farmerWorkspace")}</div>
            <div className="workspace-name">{isAdmin ? t("nav.controlCentre") : t("nav.myFarm")}</div>
          </div>
          <span className="workspace-icon" aria-hidden>
            {isAdmin ? <Shield size={16} /> : <Sprout size={16} />}
          </span>
        </div>
        <nav aria-label={t("nav.main")}>
          {links(FARMER_LINKS)}
          {isAdmin && (
            <>
              <div className="nav-section">{t("nav.administration")}</div>
              {links(ADMIN_LINKS)}
            </>
          )}
        </nav>
        <div className="sidebar-foot">
          <div className="user-chip">
            <span className="avatar" aria-hidden>
              {user?.full_name?.[0] || "?"}
            </span>
            <div>
              <div className="user-name">{user?.full_name}</div>
              <div className="muted small">{user?.preferred_language?.name}</div>
            </div>
          </div>
          <button
            className="btn btn-ghost btn-block"
            onClick={() => {
              logout();
              navigate("/login");
            }}
          >
            <LogOut size={18} /> {t("nav.logout")}
          </button>
          <div className="sidebar-motto">
            <strong>KRISHIMITRA</strong>
            {t("nav.motto")}
          </div>
        </div>
      </aside>
      {open && <div className="scrim" onClick={() => setOpen(false)} aria-hidden />}
      <div className="main">
        <header className="topbar">
          <button className="icon-btn menu-btn" onClick={() => setOpen(true)} aria-label={t("nav.openMenu")}>
            <Menu size={22} />
          </button>
          <span className="topbar-brand"><Logo size={34} tagline={null} /></span>
          <span className="topbar-spacer" />
          <button className="icon-btn help-btn" onClick={() => setGuide(true)} aria-label={t("guide.open")} title={t("guide.open")}>
            <HelpCircle size={20} />
          </button>
          <UiLanguageSwitch />
          <ThemeSwitch />
          <div className="topbar-user">
            <div>
              <div className="user-name">{user?.full_name}</div>
              <span className="role-badge">{isAdmin ? t("nav.roleAdmin") : t("nav.roleFarmer")}</span>
            </div>
            <span className="topbar-avatar" aria-hidden>
              {user?.full_name?.[0] || "?"}
            </span>
          </div>
        </header>
        <main className="content">
          <Outlet />
        </main>
      </div>
      <NowPlaying />
      <FollowProfileLanguage />
      <UserGuide open={guide} onClose={closeGuide} isAdmin={isAdmin} />
    </div>
    </SpeechProvider>
  );
}
