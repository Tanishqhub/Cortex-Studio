import { useEffect, useState } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { getCurrentUser } from "./api";
import Navbar from "./components/Navbar";
import Login from "./pages/Login";
import Signup from "./pages/Signup";
import WorkspaceList from "./pages/WorkspaceList";
import Workspace from "./pages/Workspace";
import Marketplace from "./pages/Marketplace";
import ArtifactDetail from "./pages/ArtifactDetail";
import "./App.css";

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
    <>
      {user && <Navbar user={user} onLoggedOut={() => setUser(null)} />}
      <Routes>
        <Route path="/login" element={<Login onAuthed={setUser} />} />
        <Route path="/signup" element={<Signup onAuthed={setUser} />} />
        <Route
          path="/"
          element={
            <RequireAuth user={user} loading={loading}>
              <Navigate to="/workspaces" replace />
            </RequireAuth>
          }
        />
        <Route
          path="/workspaces"
          element={
            <RequireAuth user={user} loading={loading}>
              {user && <WorkspaceList />}
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
        <Route
          path="/marketplace"
          element={
            <RequireAuth user={user} loading={loading}>
              {user && <Marketplace />}
            </RequireAuth>
          }
        />
        <Route
          path="/marketplace/:id"
          element={
            <RequireAuth user={user} loading={loading}>
              {user && <ArtifactDetail />}
            </RequireAuth>
          }
        />
      </Routes>
    </>
  );
}
