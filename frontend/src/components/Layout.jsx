import { useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import {
  BookOpen,
  CloudSun,
  FileText,
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

const FARMER_LINKS = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/assistant", label: "Voice assistant", icon: Mic },
  { to: "/disease", label: "Disease detection", icon: Leaf },
  { to: "/items", label: "Farm item scanner", icon: PackageSearch },
  { to: "/weather", label: "Weather", icon: CloudSun },
  { to: "/knowledge", label: "Knowledge base", icon: BookOpen },
  { to: "/history", label: "History", icon: History },
  { to: "/profile", label: "Profile", icon: User },
];

const ADMIN_LINKS = [
  { to: "/admin", label: "Admin overview", icon: Shield, end: true },
  { to: "/admin/users", label: "Users", icon: Users },
  { to: "/admin/documents", label: "Documents", icon: FileText },
];

export default function Layout() {
  const { user, isAdmin, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();

  const links = (items) =>
    items.map(({ to, label, icon: Icon, end }) => (
      <NavLink key={to} to={to} end={end} className="nav-link" onClick={() => setOpen(false)}>
        <Icon size={18} aria-hidden /> <span>{label}</span>
      </NavLink>
    ));

  return (
    <SpeechProvider>
    <div className="app-shell">
      <aside className={`sidebar ${open ? "open" : ""}`}>
        <div className="brand">
          <Logo size={42} tone="light" />
          <button className="icon-btn sidebar-close" onClick={() => setOpen(false)} aria-label="Close menu">
            <X size={20} />
          </button>
        </div>
        <div className="workspace-card">
          <div>
            <div className="workspace-kicker">{isAdmin ? "Admin workspace" : "Farmer workspace"}</div>
            <div className="workspace-name">{isAdmin ? "Control centre" : "My farm"}</div>
          </div>
          <span className="workspace-icon" aria-hidden>
            {isAdmin ? <Shield size={16} /> : <Sprout size={16} />}
          </span>
        </div>
        <nav aria-label="Main">
          {links(FARMER_LINKS)}
          {isAdmin && (
            <>
              <div className="nav-section">Administration</div>
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
            <LogOut size={18} /> Log out
          </button>
          <div className="sidebar-motto">
            <strong>KRISHIMITRA</strong>
            Listen · Understand · Advise
          </div>
        </div>
      </aside>
      {open && <div className="scrim" onClick={() => setOpen(false)} aria-hidden />}
      <div className="main">
        <header className="topbar">
          <button className="icon-btn menu-btn" onClick={() => setOpen(true)} aria-label="Open menu">
            <Menu size={22} />
          </button>
          <span className="topbar-brand"><Logo size={34} tagline={null} /></span>
          <span className="topbar-spacer" />
          <ThemeSwitch />
          <div className="topbar-user">
            <div>
              <div className="user-name">{user?.full_name}</div>
              <span className="role-badge">{isAdmin ? "Admin" : "Farmer"}</span>
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
    </div>
    </SpeechProvider>
  );
}
