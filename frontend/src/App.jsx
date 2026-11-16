import { lazy, Suspense } from "react";
import { BrowserRouter, Link, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import { AdminRoute, GuestRoute, ProtectedRoute } from "./components/RouteGuards";
import { PageLoader } from "./components/ui";
import { AuthProvider } from "./context/AuthContext";
import { ToastProvider } from "./context/ToastContext";
import Landing from "./pages/Landing";
import Login from "./pages/Login";
import Register from "./pages/Register";

// Heavier pages (charts, recorder) load only when opened
const Dashboard = lazy(() => import("./pages/Dashboard"));
const VoiceAssistant = lazy(() => import("./pages/VoiceAssistant"));
const DiseaseDetection = lazy(() => import("./pages/DiseaseDetection"));
const ItemScanner = lazy(() => import("./pages/ItemScanner"));
const Weather = lazy(() => import("./pages/Weather"));
const Knowledge = lazy(() => import("./pages/Knowledge"));
const History = lazy(() => import("./pages/History"));
const Profile = lazy(() => import("./pages/Profile"));
const AdminDashboard = lazy(() => import("./pages/admin/AdminDashboard"));
const AdminUsers = lazy(() => import("./pages/admin/AdminUsers"));
const AdminDocuments = lazy(() => import("./pages/admin/AdminDocuments"));

function NotFound() {
  return (
    <div className="auth-page">
      <div className="auth-card">
        <h1>Page not found</h1>
        <p className="muted">The page you opened does not exist.</p>
        <Link to="/" className="btn btn-primary">
          Go home
        </Link>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <ToastProvider>
        <AuthProvider>
          <Suspense fallback={<PageLoader />}>
            <Routes>
              <Route path="/" element={<Landing />} />
              <Route element={<GuestRoute />}>
                <Route path="/login" element={<Login />} />
                <Route path="/register" element={<Register />} />
              </Route>
              <Route element={<ProtectedRoute />}>
                <Route element={<Layout />}>
                  <Route path="/dashboard" element={<Dashboard />} />
                  <Route path="/assistant" element={<VoiceAssistant />} />
                  <Route path="/disease" element={<DiseaseDetection />} />
                  <Route path="/items" element={<ItemScanner />} />
                  <Route path="/weather" element={<Weather />} />
                  <Route path="/knowledge" element={<Knowledge />} />
                  <Route path="/history" element={<History />} />
                  <Route path="/profile" element={<Profile />} />
                  <Route element={<AdminRoute />}>
                    <Route path="/admin" element={<AdminDashboard />} />
                    <Route path="/admin/users" element={<AdminUsers />} />
                    <Route path="/admin/documents" element={<AdminDocuments />} />
                  </Route>
                </Route>
              </Route>
              <Route path="*" element={<NotFound />} />
            </Routes>
          </Suspense>
        </AuthProvider>
      </ToastProvider>
    </BrowserRouter>
  );
}
