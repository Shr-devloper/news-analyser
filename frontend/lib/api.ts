// Thin typed wrapper around the backend REST API.

const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const PREFIX = "/api/v1";

const TOKEN_KEY = "news_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string) {
  window.localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
  window.localStorage.removeItem(TOKEN_KEY);
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  auth = true
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  if (auth) {
    const token = getToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }
  const res = await fetch(`${API_URL}${PREFIX}${path}`, { ...options, headers });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {
      /* ignore */
    }
    throw new Error(typeof detail === "string" ? detail : "Request failed");
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export const api = {
  baseUrl: API_URL + PREFIX,
  async login(email: string, password: string) {
    const form = new URLSearchParams();
    form.set("username", email);
    form.set("password", password);
    const res = await fetch(`${API_URL}${PREFIX}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: form.toString(),
    });
    if (!res.ok) throw new Error("Invalid credentials");
    const data = await res.json();
    setToken(data.access_token);
    return data;
  },
  register: (email: string, password: string, full_name?: string) =>
    request("/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password, full_name }),
    }, false),
  me: () => request<any>("/auth/me"),
  reports: (params = "") => request<any[]>(`/reports${params}`),
  latestReport: () => request<any>("/reports/latest"),
  report: (id: number) => request<any>(`/reports/${id}`),
  getPreferences: () => request<any>("/preferences"),
  updatePreferences: (body: any) =>
    request("/preferences", { method: "PUT", body: JSON.stringify(body) }),
  sources: () => request<any[]>("/sources"),
  analyticsOverview: () => request<any>("/analytics/overview"),
  analyticsCategories: () => request<any[]>("/analytics/categories"),
  analyticsSources: () => request<any[]>("/analytics/sources"),
  analyticsEmail: () => request<any>("/analytics/email"),
  runPipeline: () =>
    request("/admin/pipeline/run?send_email=false", { method: "POST" }),
  downloadUrl: (id: number, fmt: string) =>
    `${API_URL}${PREFIX}/reports/${id}/download/${fmt}`,
};
