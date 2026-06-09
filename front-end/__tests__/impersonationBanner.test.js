/**
 * Contract test for components/ImpersonationBanner.js — how it reads the
 * /api/user response. When userinfo.impersonator is set (the operator's email,
 * added by the backend when an admin is "logged in as" this user), the banner
 * shows it plus a "Return to admin" link; otherwise it renders nothing.
 */
import { render, screen, waitFor } from "@testing-library/react";

import ImpersonationBanner from "../components/ImpersonationBanner";

function mockFetchJson(body, ok = true) {
  global.fetch = jest.fn().mockResolvedValue({ ok, json: async () => body });
}

beforeEach(() => {
  jest.clearAllMocks();
});

test("shows the banner with the operator email when impersonating", async () => {
  mockFetchJson({
    status: "success",
    userinfo: { email: "victim@example.com", impersonator: "operator@example.com" },
  });
  render(<ImpersonationBanner />);

  await waitFor(() => expect(screen.getByText("operator@example.com")).toBeInTheDocument());
  const link = screen.getByText("Return to admin");
  expect(link.getAttribute("href")).toContain("/admin/api/impersonate/stop");
});

test("renders nothing when not impersonating", async () => {
  mockFetchJson({ status: "success", userinfo: { email: "normal@example.com" } });
  const { container } = render(<ImpersonationBanner />);
  // Give the effect a chance to run; nothing should appear.
  await waitFor(() => expect(global.fetch).toHaveBeenCalled());
  expect(container).toBeEmptyDOMElement();
});

test("renders nothing when /api/user is unauthorized", async () => {
  mockFetchJson({}, false);
  const { container } = render(<ImpersonationBanner />);
  await waitFor(() => expect(global.fetch).toHaveBeenCalled());
  expect(container).toBeEmptyDOMElement();
});
