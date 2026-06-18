/**
 * API client for the Due Diligence Copilot backend.
 * Handles token management, request/response typing, and SSE streaming.
 */

import type {
  TokenResponse,
  Project,
  Document,
  AnalysisRun,
  ChatMessage,
  HealthResponse,
} from "@/types";

const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1").replace(/\/+$/, "");

// ── Token Management ────────────────────────────────────────────────────────

function getTokens() {
  if (typeof window === "undefined") return { access: null, refresh: null };
  return {
    access: localStorage.getItem("access_token"),
    refresh: localStorage.getItem("refresh_token"),
  };
}

function setTokens(tokens: TokenResponse) {
  localStorage.setItem("access_token", tokens.access_token);
  localStorage.setItem("refresh_token", tokens.refresh_token);
}

function clearTokens() {
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
}

// ── Base Fetch ──────────────────────────────────────────────────────────────

async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
  skipAuth = false
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  if (!skipAuth) {
    const { access } = getTokens();
    if (access) {
      headers["Authorization"] = `Bearer ${access}`;
    }
  }

  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers,
  });

  if (res.status === 401 && !skipAuth) {
    // Try refresh
    const refreshed = await refreshToken();
    if (refreshed) {
      headers["Authorization"] = `Bearer ${getTokens().access}`;
      const retryRes = await fetch(`${API_URL}${path}`, { ...options, headers });
      if (!retryRes.ok) throw new Error(await retryRes.text());
      return retryRes.json();
    }
    clearTokens();
    window.location.href = "/";
    throw new Error("Session expired");
  }

  if (!res.ok) {
    const error = await res.text();
    throw new Error(error);
  }

  if (res.status === 204) return {} as T;
  return res.json();
}

async function refreshToken(): Promise<boolean> {
  const { refresh } = getTokens();
  if (!refresh) return false;

  try {
    const res = await fetch(`${API_URL}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refresh }),
    });
    if (!res.ok) return false;
    const tokens: TokenResponse = await res.json();
    setTokens(tokens);
    return true;
  } catch {
    return false;
  }
}

// ── Auth ────────────────────────────────────────────────────────────────────

export async function register(email: string, password: string, fullName: string) {
  const data = await apiFetch<TokenResponse>(
    "/auth/register",
    {
      method: "POST",
      body: JSON.stringify({ email, password, full_name: fullName }),
    },
    true
  );
  setTokens(data);
  return data;
}

export async function login(email: string, password: string) {
  const data = await apiFetch<TokenResponse>(
    "/auth/login",
    {
      method: "POST",
      body: JSON.stringify({ email, password }),
    },
    true
  );
  setTokens(data);
  return data;
}

export function logout() {
  clearTokens();
  window.location.href = "/";
}

export function isAuthenticated() {
  return !!getTokens().access;
}

// ── Projects ────────────────────────────────────────────────────────────────

export async function getProjects() {
  return apiFetch<{ projects: Project[]; total: number }>("/projects");
}

export async function createProject(name: string, description?: string) {
  return apiFetch<Project>("/projects", {
    method: "POST",
    body: JSON.stringify({ name, description }),
  });
}

export async function getProject(id: string) {
  return apiFetch<Project>(`/projects/${id}`);
}

export async function deleteProject(id: string) {
  return apiFetch<void>(`/projects/${id}`, { method: "DELETE" });
}

// ── Documents ───────────────────────────────────────────────────────────────

export async function getDocuments(projectId: string) {
  return apiFetch<{ documents: Document[]; total: number }>(
    `/projects/${projectId}/documents`
  );
}

export async function uploadDocument(
  projectId: string,
  file: File,
  docType: string = "other"
) {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("doc_type", docType);

  const { access } = getTokens();
  const res = await fetch(`${API_URL}/projects/${projectId}/documents`, {
    method: "POST",
    headers: access ? { Authorization: `Bearer ${access}` } : {},
    body: formData,
  });

  if (!res.ok) throw new Error(await res.text());
  return res.json() as Promise<Document>;
}

export async function deleteDocument(projectId: string, docId: string) {
  return apiFetch<void>(`/projects/${projectId}/documents/${docId}`, {
    method: "DELETE",
  });
}

export function subscribeToIngestion(
  projectId: string,
  docId: string,
  onEvent: (event: unknown) => void
): EventSource {
  const { access } = getTokens();
  const url = `${API_URL}/projects/${projectId}/documents/${docId}/status`;

  const eventSource = new EventSource(url);
  eventSource.onmessage = (e) => {
    try {
      onEvent(JSON.parse(e.data));
    } catch {
      onEvent(e.data);
    }
  };
  return eventSource;
}

// ── Analysis ────────────────────────────────────────────────────────────────

export async function runAnalysis(projectId: string, type: string) {
  return apiFetch<AnalysisRun>(`/projects/${projectId}/analysis/${type}`, {
    method: "POST",
  });
}

export async function getAnalysisResult(projectId: string, runId: string) {
  return apiFetch<AnalysisRun>(`/projects/${projectId}/analysis/${runId}`);
}

// ── Chat ────────────────────────────────────────────────────────────────────

export async function getChatHistory(projectId: string) {
  return apiFetch<{ messages: ChatMessage[]; total: number }>(
    `/projects/${projectId}/chat/history`
  );
}

export function sendChatMessage(
  projectId: string,
  message: string,
  onToken: (token: string) => void,
  onCitations: (citations: unknown[]) => void,
  onDone: () => void
): AbortController {
  const controller = new AbortController();
  const { access } = getTokens();

  fetch(`${API_URL}/projects/${projectId}/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(access ? { Authorization: `Bearer ${access}` } : {}),
    },
    body: JSON.stringify({ message }),
    signal: controller.signal,
  })
    .then(async (res) => {
      const reader = res.body?.getReader();
      if (!reader) return;

      const decoder = new TextDecoder();
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const text = decoder.decode(value, { stream: true });
        const lines = text.split("\n");

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            const data = line.slice(6).trim();
            if (data === "[DONE]") {
              onDone();
              return;
            }
            try {
              const parsed = JSON.parse(data);
              if (parsed.type === "token") onToken(parsed.content);
              else if (parsed.type === "citations") onCitations(parsed.citations);
              else if (parsed.type === "done") onDone();
            } catch {
              // skip unparseable
            }
          }
        }
      }
      onDone();
    })
    .catch(() => {});

  return controller;
}

// ── System ──────────────────────────────────────────────────────────────────

export async function getSystemHealth() {
  return apiFetch<HealthResponse>("/system/health");
}
