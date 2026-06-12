/**
 * Contract test for pages/login.js — pins how the login page reads the
 * /api/login response shape. This is exactly the surface an error-shape
 * unification changes: if the backend response keys change, these tests
 * fail until the frontend is updated to match.
 *
 * Runs in jsdom (Node) — no browser. Heavy/irrelevant deps (Navbar, the router,
 * toast, sweetalert) are mocked so we isolate the response-handling logic.
 */
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { toast } from "react-toastify";

import Login from "../pages/login";

const mockPush = jest.fn();

jest.mock("next/router", () => ({
  useRouter: () => ({ push: mockPush }),
}));
jest.mock("react-toastify", () => ({
  toast: { error: jest.fn(), success: jest.fn() },
  ToastContainer: () => null,
}));
jest.mock("sweetalert2", () => ({ __esModule: true, default: { fire: jest.fn() } }));
jest.mock("../components/Navbar", () => () => null);

function mockFetchJson(body, ok = true) {
  global.fetch = jest.fn().mockResolvedValue({
    ok,
    json: async () => body,
  });
}

function fillAndSubmit() {
  // fireEvent.change sets each field in a single state update (vs a keystroke
  // each), which keeps MUI's internal re-renders out of the act() noise.
  fireEvent.change(screen.getByLabelText(/email/i), {
    target: { value: "user@example.com" },
  });
  fireEvent.change(screen.getByLabelText(/password/i), {
    target: { value: "secret123" },
  });
  fireEvent.click(screen.getByRole("button", { name: /sign in/i }));
}

beforeEach(() => {
  jest.clearAllMocks();
});

test("on a success response, navigates to the home page", async () => {
  mockFetchJson({ status: "success" });
  render(<Login />);
  await fillAndSubmit();
  await waitFor(() => expect(mockPush).toHaveBeenCalledWith("/"));
});

test("on invalid credentials, shows an error toast and does not navigate", async () => {
  mockFetchJson({ status: "error", message: "Invalid credentials" });
  render(<Login />);
  await fillAndSubmit();
  await waitFor(() =>
    expect(toast.error).toHaveBeenCalledWith("Incorrect email or password.", "error")
  );
  expect(mockPush).not.toHaveBeenCalled();
});
