import { NavLink, useNavigate } from "react-router-dom";
import { logout } from "../api";

// Global top navigation shown on every authenticated page. Rendered once in
// App.jsx (not per-page) so nav + logout live in a single place.
export default function Navbar({ user, onLoggedOut }) {
  const navigate = useNavigate();

  async function handleLogout() {
    await logout();
    onLoggedOut();
    navigate("/login");
  }

  const linkClass = ({ isActive }) => "navbar-link" + (isActive ? " active" : "");

  return (
    <nav className="navbar">
      <div className="navbar-inner">
        <NavLink to="/workspaces" className="navbar-brand">
          <span className="navbar-logo">C</span>
          Cortex Studio
        </NavLink>

        <div className="navbar-links">
          <NavLink to="/workspaces" className={linkClass}>
            Workspaces
          </NavLink>
          <NavLink to="/marketplace" className={linkClass}>
            Marketplace
          </NavLink>
        </div>

        <div className="navbar-right">
          <span className="navbar-user" title={user.email}>
            {user.email}
          </span>
          <button className="navbar-logout" onClick={handleLogout}>
            Log out
          </button>
        </div>
      </div>
    </nav>
  );
}
