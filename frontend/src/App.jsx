import { useEffect, useState } from "react";
import { Navigate, Route, Routes, useNavigate } from "react-router-dom";
import { getCurrentUser, logout } from "./api";
import Login from "./pages/Login";
import Signup from "./pages/Signup";
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
    </Routes>
  );
}
