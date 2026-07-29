import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { artifactDownloadUrl, getArtifact, setArtifactVisibility } from "../api";

export default function ArtifactDetail() {
  const { id } = useParams();
  const [artifact, setArtifact] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setLoading(true);
    getArtifact(id)
      .then(setArtifact)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [id]);

  async function toggleVisibility() {
    setSaving(true);
    try {
      const updated = await setArtifactVisibility(artifact.id, !artifact.is_public);
      setArtifact((prev) => ({ ...prev, is_public: updated.is_public }));
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <p>Loading...</p>;
  if (error) return <p className="error">{error}</p>;
  if (!artifact) return <p>Artifact not found.</p>;

  return (
    <div className="artifact-detail-page">
      <header className="artifact-detail-header">
        <Link to="/marketplace">&larr; Marketplace</Link>
        <h1>{artifact.filename}</h1>
        <a className="download-button" href={artifactDownloadUrl(artifact.id)}>
          Download
        </a>
      </header>

      <dl className="artifact-meta">
        <dt>Workspace</dt>
        <dd>{artifact.workspace_name}</dd>
        <dt>User</dt>
        <dd>{artifact.user_email}</dd>
        <dt>Created</dt>
        <dd>{new Date(artifact.created_at).toLocaleString()}</dd>
        <dt>Build duration</dt>
        <dd>{artifact.duration_ms} ms</dd>
        <dt>Binary size</dt>
        <dd>{artifact.size_bytes} bytes</dd>
        <dt>Build id</dt>
        <dd>{artifact.build_id}</dd>
        <dt>Visibility</dt>
        <dd>
          <span className={"visibility-badge" + (artifact.is_public ? " public" : " private")}>
            {artifact.is_public ? "Public" : "Private"}
          </span>
          {artifact.is_owner && (
            <button className="visibility-switch-btn" onClick={toggleVisibility} disabled={saving}>
              Make {artifact.is_public ? "private" : "public"}
            </button>
          )}
        </dd>
      </dl>

      <h2>Full build log</h2>
      <pre className="build-log">{artifact.log_text || "(no compiler output)"}</pre>
    </div>
  );
}
