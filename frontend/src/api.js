const BASE = "/api";

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.error || `Request failed with status ${res.status}`);
  }
  return data;
}

export function signup(email, password) {
  return request("/auth/signup", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export function login(email, password) {
  return request("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export function logout() {
  return request("/auth/logout", { method: "POST" });
}

export async function getCurrentUser() {
  const res = await fetch(`${BASE}/auth/me`, { credentials: "include" });
  if (res.status === 401) return null;
  if (!res.ok) throw new Error("failed to fetch current user");
  return res.json();
}

export function listWorkspaces() {
  return request("/workspaces");
}

export function createWorkspace(name) {
  return request("/workspaces", { method: "POST", body: JSON.stringify({ name }) });
}

export function getWorkspace(id) {
  return request(`/workspaces/${id}`);
}

export function deleteWorkspace(id) {
  return request(`/workspaces/${id}`, { method: "DELETE" });
}

export async function uploadA2L(id, file) {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${BASE}/workspaces/${id}/a2l`, {
    method: "POST",
    credentials: "include",
    body: form,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `Request failed with status ${res.status}`);
  return data;
}

export function getSignals(id) {
  return request(`/workspaces/${id}/signals`);
}

export function getSource(id) {
  return request(`/workspaces/${id}/source`);
}

export function saveSource(id, code) {
  return request(`/workspaces/${id}/source`, { method: "PUT", body: JSON.stringify({ code }) });
}

export function signalsHeaderUrl(id) {
  return `${BASE}/workspaces/${id}/signals.h`;
}
