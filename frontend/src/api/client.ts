import type {
  ConnectRequest,
  ConnectResponse,
  StartRequest,
  StartResponse,
  ApprovalRequest,
  SessionStateResponse,
  AppConfig,
} from "../types";

const BASE = "/api";

async function request<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `HTTP ${res.status}`);
  }
  return res.json();
}

/* ── Sheet Connection ── */
export function connectSheet(data: ConnectRequest) {
  return request<ConnectResponse>("/connect", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

/* ── Start Pipeline ── */
export function startPipeline(data: StartRequest) {
  return request<StartResponse>("/start", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

/* ── HITL 1: KR Approval ── */
export function approveKo(sessionId: string, data: ApprovalRequest) {
  return request<{ status: string }>(`/approve-ko/${sessionId}`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

/* ── HITL 2: Final Approval ── */
export function approveFinal(sessionId: string, data: ApprovalRequest) {
  return request<{
    status: string;
    updates_count?: number;
    translations_applied?: boolean;
  }>(`/approve-final/${sessionId}`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

/* ── Cancel ── */
export function cancelTranslation(sessionId: string) {
  return request<{ status: string }>(`/cancel/${sessionId}`, {
    method: "POST",
  });
}

/* ── Session State ── */
export function getSessionState(sessionId: string) {
  return request<SessionStateResponse>(`/state/${sessionId}`);
}

/* ── Backend Logs (디버그) ── */
export interface LogsResponse {
  session_id: string;
  current_step: string;
  logs: string[];
}

export function getLogs(sessionId: string) {
  return request<LogsResponse>(`/logs/${sessionId}`);
}

/* ── Downloads ── */
export function getDownloadUrl(sessionId: string, fileType: string) {
  return `${BASE}/download/${sessionId}/${fileType}`;
}

/* ── Guide ── */
export interface GuideSection {
  id: string;
  title: string;
  content: string;
}

export interface GuideResponse {
  title: string;
  sections: GuideSection[];
}

export function getGuide() {
  return request<GuideResponse>("/guide");
}

/* ── Config ── */
export function getConfig() {
  return request<AppConfig>("/config");
}

export function saveConfig(data: Partial<AppConfig>) {
  return request<{ status: string }>("/config", {
    method: "PUT",
    body: JSON.stringify(data),
  });
}
