import axios, { AxiosError, AxiosInstance, InternalAxiosRequestConfig } from "axios";

/**
 * Mage Books SAAS — Centralized Axios Singleton (Directive 9 & Sprint B).
 *
 * Capabilities:
 * 1. Automatic cookie forwarding (withCredentials: true) for HttpOnly access_token & refresh_token.
 * 2. Automatic CSRF token injection (X-CSRFToken) from browser cookies.
 * 3. Automatic Tenant ID header injection (X-Tenant-ID & X-Organization-ID).
 * 4. Concurrency-Resilient 401 Token Refresh Mutex:
 *    When multiple concurrent requests fail with 401 (e.g. on dashboard load or PWA reconnect),
 *    only ONE /refresh call is dispatched while other in-flight requests are queued in failedQueue.
 *    This prevents SimpleJWT blacklisted-token collision race conditions.
 */

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// Storage key for active tenant organization ID
export const ACTIVE_TENANT_STORAGE_KEY = "magebooks_active_tenant_id";

export function getActiveTenantId(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(ACTIVE_TENANT_STORAGE_KEY);
}

export function setActiveTenantId(tenantId: string): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(ACTIVE_TENANT_STORAGE_KEY, tenantId);
}

export function clearActiveTenantId(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(ACTIVE_TENANT_STORAGE_KEY);
}

function getCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(new RegExp(`(^|;\\s*)(${name})=([^;]*)`));
  return match ? decodeURIComponent(match[3]) : null;
}

export const apiClient: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  withCredentials: true,
  headers: {
    "Content-Type": "application/json",
  },
});

// ── Global Request Interceptor ────────────────────────────────────────────────
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    // 1. Inject active tenant ID
    const tenantId = getActiveTenantId();
    if (tenantId && !config.headers["X-Tenant-ID"]) {
      config.headers["X-Tenant-ID"] = tenantId;
      config.headers["X-Organization-ID"] = tenantId;
    }

    // 2. Inject CSRF Token for state-mutating requests
    if (typeof window !== "undefined") {
      const csrfToken = getCookie("csrftoken");
      if (csrfToken && !config.headers["X-CSRFToken"]) {
        config.headers["X-CSRFToken"] = csrfToken;
      }
    }

    return config;
  },
  (error: AxiosError) => Promise.reject(error)
);

// ── Concurrency-Resilient 401 Refresh Mutex Queue ─────────────────────────────
interface QueuedRequest {
  resolve: (value?: unknown) => void;
  reject: (reason?: unknown) => void;
}

let isRefreshing = false;
let failedQueue: QueuedRequest[] = [];

const processQueue = (error: AxiosError | null) => {
  failedQueue.forEach((promise) => {
    if (error) {
      promise.reject(error);
    } else {
      promise.resolve();
    }
  });
  failedQueue = [];
};

// ── Global Response Interceptor ───────────────────────────────────────────────
apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & {
      _retry?: boolean;
    };

    // If error is not 401 or has no config, reject immediately
    if (!error.response || error.response.status !== 401 || !originalRequest) {
      return Promise.reject(error);
    }

    const requestUrl = originalRequest.url || "";

    // Do not attempt refresh on auth endpoints (login, register, refresh itself)
    if (
      requestUrl.includes("/api/v1/auth/login") ||
      requestUrl.includes("/api/v1/auth/register") ||
      requestUrl.includes("/api/v1/auth/refresh")
    ) {
      return Promise.reject(error);
    }

    // If this request already retried, reject to prevent infinite loop
    if (originalRequest._retry) {
      return Promise.reject(error);
    }

    // If already refreshing, queue this concurrent request
    if (isRefreshing) {
      return new Promise((resolve, reject) => {
        failedQueue.push({ resolve, reject });
      })
        .then(() => apiClient(originalRequest))
        .catch((err) => Promise.reject(err));
    }

    // Set mutex lock
    originalRequest._retry = true;
    isRefreshing = true;

    try {
      // Execute single token refresh against rotating refresh endpoint
      await apiClient.post("/api/v1/auth/refresh/");

      // Release queued requests successfully
      processQueue(null);

      // Retry original request
      return apiClient(originalRequest);
    } catch (refreshError) {
      const axiosRefreshErr = refreshError as AxiosError;
      processQueue(axiosRefreshErr);

      // Clear tenant on session death and redirect if in browser
      if (typeof window !== "undefined") {
        clearActiveTenantId();
        // Redirect to login if user session expired
        if (
          !window.location.pathname.includes("/login") &&
          !window.location.pathname.includes("/signup")
        ) {
          // eslint-disable-next-line @next/next/no-location-assign-relative-destination
          window.location.href = "/login?expired=true";
        }
      }

      return Promise.reject(refreshError);
    } finally {
      isRefreshing = false;
    }
  }
);

export default apiClient;
