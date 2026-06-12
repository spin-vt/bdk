/**
 * Contract test for components/FileEditTable.js — how it reads the
 * /api/networkfiles response shape. The backend returns
 * {status:'success', files_data:[...]} or {status:'error', message:'...'} (the
 * standard shape). This pins that the error path surfaces `message` (line 54
 * historically read `.error`, which is always undefined — a latent bug this
 * test catches; it's exactly the inconsistency the error-shape unification removes).
 */
import { render, screen, waitFor } from "@testing-library/react";
import { toast } from "react-toastify";

import FileEditTable from "../components/FileEditTable";

jest.mock("react-toastify", () => ({
  toast: { error: jest.fn(), success: jest.fn() },
  ToastContainer: () => null,
}));

function mockFetchJson(body, ok = true) {
  global.fetch = jest.fn().mockResolvedValue({ ok, json: async () => body });
}

beforeEach(() => {
  jest.clearAllMocks();
});

test("on a networkfiles error, surfaces the server message", async () => {
  mockFetchJson({ status: "error", message: "Folder not found" });
  render(<FileEditTable folderId={1} />);
  await waitFor(() => expect(toast.error).toHaveBeenCalledWith("Folder not found"));
});

test("on success, renders the returned file names", async () => {
  mockFetchJson({
    status: "success",
    files_data: [
      { id: 1, name: "fiber.kml", maxDownloadSpeed: 100, maxUploadSpeed: 20, techType: 50 },
    ],
  });
  render(<FileEditTable folderId={1} />);
  // The name renders inside an editable MUI TextField, so it's a value.
  expect(await screen.findByDisplayValue("fiber.kml")).toBeInTheDocument();
  expect(toast.error).not.toHaveBeenCalled();
});
