/**
 * The global fetch wrapper must echo the csrf_access_token cookie (set by the
 * backend at login) as X-CSRF-TOKEN on mutating requests — the backend rejects
 * cookie-authenticated POST/PUT/PATCH/DELETE without it.
 */

import { installCsrfFetch, readCsrfToken } from "../utils/csrf";

describe("csrf fetch wrapper", () => {
  let spy;

  beforeEach(() => {
    document.cookie = "csrf_access_token=tok123";
    window.__bdkCsrfFetchInstalled = false;
    spy = jest.fn().mockResolvedValue({ ok: true });
    window.fetch = spy;
    installCsrfFetch();
  });

  it("reads the csrf cookie", () => {
    expect(readCsrfToken()).toBe("tok123");
  });

  it("adds the header to mutating requests", async () => {
    await window.fetch("/api/update_profile", { method: "POST", body: "{}" });
    const init = spy.mock.calls[0][1];
    expect(new Headers(init.headers).get("X-CSRF-TOKEN")).toBe("tok123");
  });

  it("preserves existing headers", async () => {
    await window.fetch("/api/x", {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
    });
    const headers = new Headers(spy.mock.calls[0][1].headers);
    expect(headers.get("Content-Type")).toBe("application/json");
    expect(headers.get("X-CSRF-TOKEN")).toBe("tok123");
  });

  it("leaves GET requests alone", async () => {
    await window.fetch("/api/user");
    const init = spy.mock.calls[0][1];
    expect(init === undefined || !new Headers(init.headers).get("X-CSRF-TOKEN")).toBe(true);
  });

  it("installs only once", () => {
    const wrapped = window.fetch;
    installCsrfFetch();
    expect(window.fetch).toBe(wrapped);
  });
});
