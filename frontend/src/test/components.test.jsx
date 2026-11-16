import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import LanguageSelect from "../components/LanguageSelect";
import SourceList from "../components/SourceList";
import { ConfidenceBar } from "../components/ui";
import { AuthProvider } from "../context/AuthContext";
import { ToastProvider } from "../context/ToastContext";
import Login from "../pages/Login";
import Register from "../pages/Register";

vi.mock("../api/endpoints", () => ({
  meta: { languages: vi.fn(() => Promise.resolve([
    { code: "te", name: "Telugu", native_name: "తెలుగు" },
    { code: "en", name: "English", native_name: "English" },
  ])) },
  auth: { login: vi.fn(), register: vi.fn(), profile: vi.fn(), logout: vi.fn(() => Promise.resolve()) },
  assistant: { fetchBlob: vi.fn() },
}));

import { auth } from "../api/endpoints";

const wrap = (ui) =>
  render(
    <MemoryRouter>
      <ToastProvider>
        <AuthProvider>{ui}</AuthProvider>
      </ToastProvider>
    </MemoryRouter>,
  );

beforeEach(() => vi.clearAllMocks());

describe("ConfidenceBar", () => {
  it("shows the percentage and colour band", () => {
    const { container } = render(<ConfidenceBar value={0.42} />);
    expect(screen.getByText("42%")).toBeInTheDocument();
    expect(container.querySelector(".confidence-low")).not.toBeNull();
  });
});

describe("SourceList", () => {
  it("lists sources with page numbers", () => {
    render(<SourceList sources={[{ index: 1, title: "Paddy guide", page: 4, snippet: "Keep 5 cm water", kind: "document" }]} />);
    expect(screen.getByText("1 source")).toBeInTheDocument();
    expect(screen.getByText("[1] Paddy guide, p. 4")).toBeInTheDocument();
  });
  it("renders nothing without sources", () => {
    const { container } = render(<SourceList sources={[]} />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe("LanguageSelect", () => {
  it("loads languages from the API and shows native names", async () => {
    const onChange = vi.fn();
    render(<LanguageSelect value="te" onChange={onChange} />);
    expect(await screen.findByRole("option", { name: "తెలుగు (Telugu)" })).toBeInTheDocument();
    await userEvent.selectOptions(screen.getByRole("combobox"), "en");
    expect(onChange).toHaveBeenCalledWith("en");
  });
});

describe("Login page", () => {
  it("asks for both fields before calling the API", async () => {
    wrap(<Login />);
    await userEvent.click(screen.getByRole("button", { name: /log in/i }));
    expect(screen.getByRole("alert")).toHaveTextContent(/mobile number/i);
    expect(auth.login).not.toHaveBeenCalled();
  });
  it("shows the server's error message on wrong password", async () => {
    auth.login.mockRejectedValueOnce({ response: { status: 401, data: { error: { message: "Incorrect mobile number/email or password" } } } });
    wrap(<Login />);
    await userEvent.type(screen.getByLabelText(/mobile number or email/i), "9876543210");
    await userEvent.type(screen.getByLabelText(/password/i), "Wrong1234");
    await userEvent.click(screen.getByRole("button", { name: /log in/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Incorrect mobile number/email or password");
    expect(auth.login).toHaveBeenCalledWith("9876543210", "Wrong1234");
  });
});

describe("Register page", () => {
  it("validates fields and sends a cleaned payload", async () => {
    auth.register.mockResolvedValueOnce({ access_token: "t", user: { id: 1, role: "farmer", full_name: "Ravi" } });
    wrap(<Register />);
    await userEvent.click(screen.getByRole("button", { name: /register/i }));
    expect(screen.getByText("Enter your name")).toBeInTheDocument();
    expect(auth.register).not.toHaveBeenCalled();

    await userEvent.type(screen.getByLabelText(/full name/i), "Ravi Kumar");
    await userEvent.type(screen.getByLabelText(/^mobile number/i), "+91 98765 43210");
    await userEvent.type(screen.getByLabelText(/^password/i), "Farmer123");
    await userEvent.type(screen.getByLabelText(/confirm password/i), "Farmer123");
    await userEvent.click(screen.getByRole("button", { name: /register/i }));
    await waitFor(() => expect(auth.register).toHaveBeenCalled());
    expect(auth.register.mock.calls[0][0]).toEqual({
      full_name: "Ravi Kumar",
      phone: "9876543210",
      password: "Farmer123",
      preferred_language: "te",
    });
  });
});
