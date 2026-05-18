const RUNTIME_TARGET = import.meta.env.VITE_RUNTIME_TARGET ?? (import.meta.env.DEV ? "local" : "remote");
const API_BASE_URL =
  RUNTIME_TARGET === "local"
    ? ""
    : (import.meta.env.VITE_REMOTE_API_BASE_URL ?? import.meta.env.VITE_API_BASE_URL ?? "");
const TOKEN_KEY = "compute_rental_access_token";

let accessToken = "";

export function setAccessToken(token) {
  accessToken = token ?? "";
}

function getStoredToken() {
  if (typeof window === "undefined") {
    return accessToken;
  }
  return accessToken || window.localStorage.getItem(TOKEN_KEY) || "";
}

function buildHeaders(options = {}) {
  const headers = {
    ...(options.headers ?? {})
  };
  if (options.body) {
    headers["Content-Type"] = "application/json";
  }
  const token = getStoredToken();
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  return headers;
}

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: buildHeaders(options),
    ...options
  });

  const contentType = response.headers.get("content-type") ?? "";
  const payload = contentType.includes("application/json") ? await response.json() : null;

  if (!response.ok) {
    if (payload?.error?.message) {
      throw new Error(payload.error.message);
    }
    if (payload?.message) {
      throw new Error(payload.message);
    }
    throw new Error("请求失败");
  }

  if (payload?.success === false) {
    throw new Error(payload?.error?.message ?? payload?.message ?? "请求失败");
  }

  return payload;
}

export function getLocationsSummary() {
  return request("/api/locations/summary");
}

export function getCards() {
  return request("/api/cards");
}

export function createRental(body) {
  return request("/api/rentals", {
    method: "POST",
    body: JSON.stringify(body)
  });
}

export function getRentalDetail(rentalId) {
  return request(`/api/rentals/${rentalId}`);
}

export function cancelRental(rentalId) {
  return request(`/api/rentals/${rentalId}/cancel`, {
    method: "POST"
  });
}

export function register(body) {
  return request("/api/auth/register", {
    method: "POST",
    body: JSON.stringify(body)
  });
}

export function login(body) {
  return request("/api/auth/login", {
    method: "POST",
    body: JSON.stringify(body)
  });
}

export function logout() {
  return request("/api/auth/logout", {
    method: "POST"
  });
}

export function getMe() {
  return request("/api/me");
}

export function getDashboard() {
  return request("/api/me/dashboard");
}

export function rechargeBalance(amount) {
  return request("/api/me/balance/recharge", {
    method: "POST",
    body: JSON.stringify({ amount })
  });
}

export { API_BASE_URL };
