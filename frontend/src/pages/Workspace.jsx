import Editor from "@monaco-editor/react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  getBuild,
  getSignals,
  getSource,
  getWorkspace,
  saveSource,
  signalsHeaderUrl,
  triggerBuild,
  uploadA2L,
} from "../api";

const BUILD_POLL_INTERVAL_MS = 800;

const STARTER_TEMPLATE = `#include "signals.h"

int main(void) {
    /* Read/write signals declared in signals.h here. */
    return 0;
}
`;

// Mirrors backend/app/header_gen.py::sanitise_identifier -- kept in sync so
// clicking a signal in the panel inserts the exact identifier signals.h
// will declare. See docs/DECISIONS.md.
function sanitiseIdentifier(name) {
  let ident = name.replace(/[^A-Za-z0-9_]/g, "_");
  if (/^[0-9]/.test(ident)) ident = "_" + ident;
  return ident || "_";
}

export default function Workspace() {
  const { id } = useParams();
  const [workspace, setWorkspace] = useState(null);
  const [signals, setSignals] = useState(null);
  const [signalsError, setSignalsError] = useState("");
  const [code, setCode] = useState(STARTER_TEMPLATE);
  const [loading, setLoading] = useState(true);
  const [saveState, setSaveState] = useState("idle"); // idle | saving | saved | error
  const [uploadError, setUploadError] = useState("");
  const [filter, setFilter] = useState("");
  const [build, setBuild] = useState(null); // latest build's status payload (poll target)
  const [buildError, setBuildError] = useState("");
  const editorRef = useRef(null);
  const pollTimeoutRef = useRef(null);

  useEffect(() => {
    setLoading(true);
    Promise.all([getWorkspace(id), getSource(id)])
      .then(([ws, src]) => {
        setWorkspace(ws);
        setCode(src.code || STARTER_TEMPLATE);
      })
      .finally(() => setLoading(false));
    loadSignals();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  function loadSignals() {
    setSignalsError("");
    getSignals(id)
      .then(setSignals)
      .catch((err) => {
        setSignals(null);
        setSignalsError(err.message);
      });
  }

  async function handleSave() {
    setSaveState("saving");
    try {
      await saveSource(id, code);
      setSaveState("saved");
      setTimeout(() => setSaveState("idle"), 1500);
    } catch {
      setSaveState("error");
    }
  }

  async function handleUpload(e) {
    const file = e.target.files[0];
    e.target.value = "";
    if (!file) return;
    setUploadError("");
    try {
      await uploadA2L(id, file);
      const ws = await getWorkspace(id);
      setWorkspace(ws);
      loadSignals();
    } catch (err) {
      setUploadError(err.message);
    }
  }

  useEffect(() => {
    return () => clearTimeout(pollTimeoutRef.current);
  }, []);

  function pollBuild(buildId) {
    getBuild(buildId)
      .then((b) => {
        setBuild(b);
        if (b.status === "queued" || b.status === "running") {
          pollTimeoutRef.current = setTimeout(() => pollBuild(buildId), BUILD_POLL_INTERVAL_MS);
        }
      })
      .catch((err) => setBuildError(err.message));
  }

  async function handleCompile() {
    setBuildError("");
    clearTimeout(pollTimeoutRef.current);
    try {
      // Compile always runs against the last-saved source, so make sure
      // unsaved edits go out first -- otherwise a "Compile" click after
      // typing would silently build stale code.
      await saveSource(id, code);
      const created = await triggerBuild(id);
      setBuild(created);
      pollTimeoutRef.current = setTimeout(() => pollBuild(created.id), BUILD_POLL_INTERVAL_MS);
    } catch (err) {
      setBuildError(err.message);
    }
  }

  function insertSignal(signal) {
    const ident = sanitiseIdentifier(signal.name);
    const editor = editorRef.current;
    if (!editor) return;
    const selection = editor.getSelection();
    editor.executeEdits("insert-signal", [{ range: selection, text: ident, forceMoveMarkers: true }]);
    editor.focus();
  }

  const measurements = signals?.measurements || [];
  const filtered = useMemo(() => {
    const q = filter.trim().toLowerCase();
    if (!q) return measurements;
    return measurements.filter((s) => s.name.toLowerCase().includes(q));
  }, [measurements, filter]);

  if (loading) return <p>Loading...</p>;
  if (!workspace) return <p>Workspace not found.</p>;

  return (
    <div className="workspace-page">
      <header className="workspace-header">
        <Link to="/workspaces">&larr; Workspaces</Link>
        <h1>{workspace.name}</h1>
        <div className="workspace-header-actions">
          <label className="upload-button">
            Upload A2L
            <input type="file" accept=".a2l" onChange={handleUpload} hidden />
          </label>
          {workspace.a2l_file && (
            <a href={signalsHeaderUrl(id)} target="_blank" rel="noreferrer">
              View signals.h
            </a>
          )}
          <button onClick={handleSave} disabled={saveState === "saving"}>
            {saveState === "saving" ? "Saving..." : saveState === "saved" ? "Saved" : "Save"}
          </button>
          <button
            onClick={handleCompile}
            disabled={build?.status === "queued" || build?.status === "running"}
          >
            {build?.status === "queued" || build?.status === "running" ? "Compiling..." : "Compile"}
          </button>
        </div>
      </header>
      {uploadError && <p className="error">{uploadError}</p>}
      {saveState === "error" && <p className="error">Failed to save source.</p>}
      {buildError && <p className="error">{buildError}</p>}

      <div className="workspace-body">
        <aside className="signal-panel">
          <h2>Signals</h2>
          {signalsError ? (
            <p className="error">{signalsError}</p>
          ) : (
            <>
              <input
                type="text"
                placeholder={`Search ${measurements.length} signals...`}
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
              />
              <ul className="signal-list">
                {filtered.map((s) => (
                  <li key={s.name} onClick={() => insertSignal(s)} title="Click to insert into editor">
                    <div className="signal-name">{sanitiseIdentifier(s.name)}</div>
                    <div className="signal-meta">
                      {s.datatype || "?"} &middot; {s.direction}
                      {s.limits && s.limits.lower !== null && s.limits.upper !== null
                        ? ` · [${s.limits.lower}, ${s.limits.upper}]`
                        : ""}
                    </div>
                  </li>
                ))}
              </ul>
            </>
          )}
        </aside>

        <main className="editor-pane">
          <Editor
            height="70vh"
            defaultLanguage="c"
            value={code}
            onChange={(value) => setCode(value ?? "")}
            onMount={(editor) => {
              editorRef.current = editor;
            }}
            options={{ minimap: { enabled: false }, fontSize: 14 }}
          />

          {build && (
            <section className="build-console">
              <div className="build-console-header">
                <span className={`build-status build-status-${build.status}`}>{build.status}</span>
                {build.duration_ms != null && <span>{build.duration_ms} ms</span>}
                {build.exit_code != null && <span>exit code {build.exit_code}</span>}
              </div>
              <pre className="build-log">
                {build.log_text
                  ? build.log_text
                  : build.status === "queued" || build.status === "running"
                    ? "Compiling..."
                    : "(no compiler output)"}
              </pre>
            </section>
          )}
        </main>
      </div>
    </div>
  );
}
