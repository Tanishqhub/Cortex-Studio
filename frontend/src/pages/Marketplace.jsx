import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listMarketplace } from "../api";

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  return `${(bytes / 1024).toFixed(1)} KB`;
}

export default function Marketplace({ user }) {
  const [artifacts, setArtifacts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    listMarketplace()
      .then(setArtifacts)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="marketplace-page">
      <header className="marketplace-header">
        <Link to="/">&larr; Home</Link>
        <h1>Marketplace</h1>
        <span>{user.email}</span>
      </header>
      <p className="marketplace-subtitle">
        Every successful build from every workspace/user, browsable and downloadable by any
        logged-in account (see docs/DECISIONS.md).
      </p>

      {error && <p className="error">{error}</p>}
      {loading ? (
        <p>Loading...</p>
      ) : artifacts.length === 0 ? (
        <p>No successful builds yet. Compile something in a workspace first.</p>
      ) : (
        <table className="marketplace-table">
          <thead>
            <tr>
              <th>Filename</th>
              <th>Workspace</th>
              <th>User</th>
              <th>Built</th>
              <th>Duration</th>
              <th>Size</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {artifacts.map((a) => (
              <tr key={a.id}>
                <td className="marketplace-filename">
                  <Link to={`/marketplace/${a.id}`}>{a.filename}</Link>
                </td>
                <td>{a.workspace_name}</td>
                <td>{a.user_email}</td>
                <td>{new Date(a.created_at).toLocaleString()}</td>
                <td>{a.duration_ms} ms</td>
                <td>{formatBytes(a.size_bytes)}</td>
                <td>
                  <Link to={`/marketplace/${a.id}`}>Details</Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
