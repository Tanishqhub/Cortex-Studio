import { useEffect, useState } from "react";
import { Link, Navigate, Route, Routes, useNavigate } from "react-router-dom";
import { getCurrentUser, logout } from "./api";
import Login from "./pages/Login";
import Signup from "./pages/Signup";
import WorkspaceList from "./pages/WorkspaceList";
import Workspace from "./pages/Workspace";
import "./App.css";

function Landing({ user, onLoggedOut }) {
  const navigate = useNavigate();

  async function handleLogout() {
    await logout();
    onLoggedOut();
    navigate("/login");
  }

  return (
    <div className="auth-page">
      <h1>Logged in as {user.email}</h1>
      <p>
        <Link to="/workspaces">Go to workspaces</Link>
      </p>
      <button onClick={handleLogout}>Logout</button>
    </div>
  );
}

function RequireAuth({ user, loading, children }) {
  if (loading) return null;
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

export default function App() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getCurrentUser()
      .then(setUser)
      .finally(() => setLoading(false));
  }, []);

  return (
    <Routes>
      <Route path="/login" element={<Login onAuthed={setUser} />} />
      <Route path="/signup" element={<Signup onAuthed={setUser} />} />
      <Route
        path="/"
        element={
          <RequireAuth user={user} loading={loading}>
            {user && <Landing user={user} onLoggedOut={() => setUser(null)} />}
          </RequireAuth>
        }
      />
      <Route
        path="/workspaces"
        element={
          <RequireAuth user={user} loading={loading}>
            {user && <WorkspaceList user={user} onLoggedOut={() => setUser(null)} />}
          </RequireAuth>
        }
      />
      <Route
        path="/workspaces/:id"
        element={
          <RequireAuth user={user} loading={loading}>
            {user && <Workspace />}
          </RequireAuth>
        }
      />
    </Routes>
  );
}
