// Double-submit CSRF support. At login the backend sets two cookies: the
// HttpOnly session `token` and a JS-readable `csrf_access_token`. Every
// mutating request must echo the latter in an X-CSRF-TOKEN header or the
// backend rejects it. Installing a global fetch wrapper once (from _app.js)
// covers every call site without touching them individually.

export function readCsrfToken() {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(/(?:^|;\s*)csrf_access_token=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : null;
}

const MUTATING = ["POST", "PUT", "PATCH", "DELETE"];

export function installCsrfFetch() {
  if (typeof window === "undefined" || window.__bdkCsrfFetchInstalled) return;
  const origFetch = window.fetch.bind(window);
  window.fetch = (input, init) => {
    const method = ((init && init.method) || (input && input.method) || "GET").toUpperCase();
    if (MUTATING.includes(method)) {
      const token = readCsrfToken();
      if (token) {
        const headers = new Headers((init && init.headers) || undefined);
        if (!headers.has("X-CSRF-TOKEN")) headers.set("X-CSRF-TOKEN", token);
        init = { ...(init || {}), headers };
      }
    }
    return origFetch(input, init);
  };
  window.__bdkCsrfFetchInstalled = true;
}
