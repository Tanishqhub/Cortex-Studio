import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listMarketplace, setArtifactVisibility } from "../api";

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  return `${(bytes / 1024).toFixed(1)} KB`;
}

const SCOPES = [
  { key: "public", label: "Public" },
  { key: "mine", label: "My Builds" },
];

export default function Marketplace() {
  const [scope, setScope] = useState("public");
  const [artifacts, setArtifacts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [pendingId, setPendingId] = useState(null);

  const load = useCallback((s) => {
    setLoading(true);
    setError("");
    listMarketplace(s)
      .then(setArtifacts)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load(scope);
  }, [scope, load]);

  async function togglePublic(artifact) {
    setPendingId(artifact.id);
    try {
      await setArtifactVisibility(artifact.id, !artifact.is_public);
      if (scope === "mine") {
        setArtifacts((prev) =>
          prev.map((a) => (a.id === artifact.id ? { ...a, is_public: !a.is_public } : a))
        );
      } else {
        setArtifacts((prev) => prev.filter((a) => a.id !== artifact.id));
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setPendingId(null);
    }
  }

  return (
    <div className="marketplace-page">
      <header className="marketplace-header">
        <div>
          <h1>Marketplace</h1>
          <p className="marketplace-subtitle">
            {scope === "public"
              ? "Builds the community has chosen to share, browsable and downloadable by any logged-in account."
              : "Every build of yours, whether or not you've made it public."}
          </p>
        </div>
        <div className="scope-toggle" role="tablist" aria-label="Marketplace scope">
          {SCOPES.map((s) => (
            <button
              key={s.key}
              role="tab"
              aria-selected={scope === s.key}
              className={"scope-toggle-btn" + (scope === s.key ? " active" : "")}
              onClick={() => setScope(s.key)}
            >
              {s.label}
            </button>
          ))}
        </div>
      </header>

      {error && <p className="error">{error}</p>}
      {loading ? (
        <p>Loading...</p>
      ) : artifacts.length === 0 ? (
        <p className="marketplace-empty">
          {scope === "public"
            ? "No public builds yet. Mark one of your builds public from “My Builds” to list it here."
            : "No builds yet. Compile something in a workspace first."}
        </p>
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
              <th>Visibility</th>
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
                  {a.is_owner ? (
                    <button
                      className={"visibility-badge toggle" + (a.is_public ? " public" : " private")}
                      onClick={() => togglePublic(a)}
                      disabled={pendingId === a.id}
                      title={a.is_public ? "Click to make private" : "Click to make public"}
                    >
                      {a.is_public ? "Public" : "Private"}
                    </button>
                  ) : (
                    <span className={"visibility-badge" + (a.is_public ? " public" : " private")}>
                      {a.is_public ? "Public" : "Private"}
                    </span>
                  )}
                </td>
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
