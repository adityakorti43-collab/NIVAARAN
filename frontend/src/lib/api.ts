import type {
  AuthUser,
  Analysis, AssistantAnswer, Bill, BillItemEdit, ClaimBundle, ClaimFacts, ClaimListEntry, Clause, Comparison, DocumentRecord,
  AuthProviders, Hypotheticals, PolicySummary, PolicyVersion, SystemInfo,
} from "./types";

export class ApiError extends Error {
  constructor(public status: number, message: string, public code?: string) {
    super(message);
  }
}

export const authEvents = new EventTarget();

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, { ...init, headers: { ...(init?.body && !(init.body instanceof FormData) ? { "Content-Type": "application/json" } : {}), ...init?.headers } });
  } catch {
    throw new ApiError(0, "Cannot reach the Nivaaran API. Is the backend running on port 8000?");
  }
  if (res.status === 401 && !path.startsWith("/api/auth/")) authEvents.dispatchEvent(new Event("unauthorized"));
  if (!res.ok) {
    let msg = `Request failed (${res.status})`;
    let code: string | undefined;
    try {
      const body = await res.json();
      msg = body.message ?? (typeof body.detail === "string" ? body.detail : Array.isArray(body.detail) ? body.detail.map((d: { msg: string; loc: string[] }) => `${d.loc.slice(1).join(".")}: ${d.msg}`).join("; ") : msg);
      code = body.error;
    } catch { /* non-JSON error */ }
    throw new ApiError(res.status, msg, code);
  }
  return res.json() as Promise<T>;
}

/** Upload with progress events (fetch has no upload progress). */
export function uploadWithProgress<T>(path: string, form: FormData, onProgress: (pct: number) => void): Promise<T> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", path);
    xhr.upload.onprogress = (e) => e.lengthComputable && onProgress(Math.round((e.loaded / e.total) * 100));
    xhr.onerror = () => reject(new ApiError(0, "Upload failed: cannot reach the Nivaaran API."));
    xhr.onload = () => {
      let body: any = null;
      try { body = JSON.parse(xhr.responseText); } catch { /* ignore */ }
      if (xhr.status >= 200 && xhr.status < 300) resolve(body as T);
      else reject(new ApiError(xhr.status, body?.message ?? (typeof body?.detail === "string" ? body.detail : `Upload failed (${xhr.status})`), body?.error));
    };
    xhr.send(form);
  });
}

const json = (body: unknown) => ({ method: "POST", body: JSON.stringify(body) });

export const api = {
  system: () => request<SystemInfo>("/api/system"),
  documents: () => request<DocumentRecord[]>("/api/documents"),
  document: (id: string) => request<DocumentRecord>(`/api/documents/${id}`),
  deleteDocument: (id: string) => request<{ deleted: string }>(`/api/documents/${id}`, { method: "DELETE" }),
  clauses: (id: string, q?: string, category?: string) =>
    request<Clause[]>(`/api/documents/${id}/clauses?${new URLSearchParams({ ...(q ? { q } : {}), ...(category ? { category } : {}) })}`),
  versions: (policyId: string) => request<{ versions: PolicyVersion[]; conflicts: string[] }>(`/api/policies/${policyId}/versions`),
  uploadDocument: (file: File, docType: "policy" | "endorsement" | "benefit_summary", onProgress: (p: number) => void) => {
    const f = new FormData();
    f.append("file", file);
    f.append("doc_type", docType);
    return uploadWithProgress<DocumentRecord>("/api/documents", f, onProgress);
  },
  parseBill: (file: File, onProgress: (p: number) => void) => {
    const f = new FormData();
    f.append("file", file);
    return uploadWithProgress<Bill>("/api/bills/parse", f, onProgress);
  },
  claims: () => request<ClaimListEntry[]>("/api/claims"),
  claim: (id: string) => request<ClaimBundle>(`/api/claims/${id}`),
  createClaim: (body: unknown) => request<{ claim: ClaimBundle["claim"]; analysis: Analysis }>("/api/claims", json(body)),
  updateClaim: (id: string, body: { facts?: ClaimFacts; admission_date?: string; discharge_date?: string; endorsement_ids?: string[]; bill_items?: BillItemEdit[]; confirm_bill?: boolean }) =>
    request<{ analysis: Analysis; comparison: Comparison | null }>(`/api/claims/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  deleteClaim: (id: string) => request<{ deleted: string }>(`/api/claims/${id}`, { method: "DELETE" }),
  scenario: (id: string, hyp: Hypotheticals) => request<{ analysis: Analysis; comparison: Comparison }>(`/api/claims/${id}/scenario`, json(hyp)),
  compareVersions: (id: string) => request<{ versions: { version: PolicyVersion; is_applicable: boolean; summary: Analysis["summary"]; comparison_vs_current: Comparison }[]; conflicts: string[] }>(`/api/claims/${id}/compare-versions`, { method: "POST" }),
  ask: (id: string, question: string, context?: Record<string, string>) => request<AssistantAnswer>(`/api/claims/${id}/ask`, json({ question, context })),
  fairness: (id: string) => request<any>(`/api/claims/${id}/fairness`),
  actions: (id: string) => request<any>(`/api/claims/${id}/actions`),
  evidence: (id: string, q: string) => request<any>(`/api/claims/${id}/evidence?${new URLSearchParams({ q })}`),
  costs: () => request<any>("/api/costs"),
  costEstimate: (body: unknown) => request<any>("/api/costs/estimate", json(body)),
  evalResults: () => request<any>("/api/evaluation/results"),
  evalRun: () => request<any>("/api/evaluation/run", { method: "POST" }),
  loadDemo: () => request<{ claim_id: string; comparison: Comparison }>("/api/demo/load", { method: "POST" }),
  enterDemo: () => request<{ claim_id: string; user: AuthUser }>("/api/demo/enter", { method: "POST" }),
  me: () => request<{ user: AuthUser }>("/api/auth/me"),
  login: (email: string, password: string) => request<{ user: AuthUser }>("/api/auth/login", json({ email, password })),
  register: (name: string, email: string, password: string) => request<{ user: AuthUser }>("/api/auth/register", json({ name, email, password })),
  logout: () => request<{ signed_out: boolean }>("/api/auth/logout", { method: "POST" }),
  updateProfile: (name: string) => request<{ user: AuthUser }>("/api/auth/me", { method: "PATCH", body: JSON.stringify({ name }) }),
  changePassword: (current_password: string, new_password: string) => request<{ changed: boolean }>("/api/auth/password", json({ current_password, new_password })),
  resetRequest: (email: string) => request<{ message: string }>("/api/auth/reset/request", json({ email })),
  resetConfirm: (token: string, new_password: string) => request<{ reset: boolean }>("/api/auth/reset/confirm", json({ token, new_password })),
  deleteAccount: () => request<{ deleted: boolean }>("/api/auth/me", { method: "DELETE" }),
  overview: () => request<any>("/api/me/overview"),
  chatHistory: (id: string) => request<any[]>(`/api/claims/${id}/chat`),
  clearChat: (id: string) => request<any>(`/api/claims/${id}/chat`, { method: "DELETE" }),
  scenarios: (id: string) => request<any[]>(`/api/claims/${id}/scenarios`),
  saveScenario: (id: string, name: string, hypotheticals: Hypotheticals) => request<any>(`/api/claims/${id}/scenarios`, json({ name, hypotheticals })),
  deleteScenario: (id: string, sid: string) => request<any>(`/api/claims/${id}/scenarios/${sid}`, { method: "DELETE" }),
  downloadUrl: (docId: string) => `/api/documents/${docId}/download`,
  explainClause: (docId: string, section: string, lang: "en" | "hi" | "mr") => request<{ text: string }>(`/api/documents/${docId}/clauses/${encodeURIComponent(section)}/explain?lang=${lang}`),
  policySummary: (docId: string, lang: "en" | "hi" | "mr") => request<PolicySummary>(`/api/documents/${docId}/summary?lang=${lang}`),
  authProviders: () => request<AuthProviders>("/api/auth/providers"),
  phoneStart: (phone: string) => request<{ phone: string; delivery: "sms" | "outbox"; masked: string; dev_code?: string }>("/api/auth/phone/start", json({ phone })),
  phoneVerify: (phone: string, code: string, name: string) => request<{ user: AuthUser }>("/api/auth/phone/verify", json({ phone, code, name })),
  translateHi: (text: string) => request<{ text: string }>("/api/translate/hi", json({ text })),
  reportUrl: (id: string, kind: "pdf" | "json") => `/api/claims/${id}/report.${kind}`,
};
