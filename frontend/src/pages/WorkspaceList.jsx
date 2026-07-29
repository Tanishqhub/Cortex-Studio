import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { createWorkspace, listWorkspaces } from "../api";

export default function WorkspaceList() {
  const [workspaces, setWorkspaces] = useState([]);
  const [loading, setLoading] = useState(true);
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const navigate = useNavigate();

  function refresh() {
    setLoading(true);
    listWorkspaces()
      .then(setWorkspaces)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }

  useEffect(refresh, []);

  async function handleCreate(e) {
    e.preventDefault();
    setError("");
    try {
      const workspace = await createWorkspace(name);
      setName("");
      navigate(`/workspaces/${workspace.id}`);
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="workspace-list-page">
      <header className="workspace-list-header">
        <h1>Workspaces</h1>
        <p className="page-subtitle">Create a workspace, upload an A2L file, and start writing C.</p>
      </header>

      <form onSubmit={handleCreate} className="workspace-create-form">
        <input
          type="text"
          placeholder="New workspace name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
        />
        <button type="submit">Create workspace</button>
      </form>
      {error && <p className="error">{error}</p>}

      {loading ? (
        <p>Loading...</p>
      ) : workspaces.length === 0 ? (
        <p>No workspaces yet. Create one above.</p>
      ) : (
        <ul className="workspace-list">
          {workspaces.map((w) => (
            <li key={w.id}>
              <Link to={`/workspaces/${w.id}`} className="workspace-card-link">
                <span className="workspace-card-name">{w.name}</span>
                <span className="workspace-meta">
                  {w.has_a2l_file ? "A2L uploaded" : "no A2L uploaded"}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
