import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import axe from "axe-core";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { SeverityBadge, StatusBadge } from "@/components/ui/Badges";
import { TextField } from "@/components/ui/Field";
import { SwipeCompare } from "@/components/ui/SwipeCompare";
import { loginSchema, registerSchema, zodErrors } from "@/features/auth/schemas";
import { CookieBanner } from "@/features/privacy/CookieBanner";
import { CONSENT_VERSION, uiStorage, useConsent } from "@/features/privacy/consent";
import { api, ApiError, buildQuery, refreshSession } from "@/lib/api/client";
import { hasRole, useAuth } from "@/lib/auth/store";
import { fmtCoord, fmtHa, SEVERITY } from "@/lib/format";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), replace: vi.fn() }), useSearchParams: () => new URLSearchParams() }));

const user = { id: "u1", email: "a@b.co", full_name: "Ana", role: "analyst" as const, is_active: true, created_at: "2026-01-01", last_login_at: null };

async function expectNoAxeViolations(container: HTMLElement) {
  const result = await axe.run(container, { rules: { "color-contrast": { enabled: false } } }); // jsdom no puede calcular colores
  expect(result.violations.map((v) => `${v.id}: ${v.help}`)).toEqual([]);
}

beforeEach(() => {
  localStorage.clear();
  useAuth.setState({ status: "unknown", accessToken: null, user: null });
  useConsent.setState({ choice: null, ready: false, panelOpen: false });
});
afterEach(() => vi.restoreAllMocks());

describe("formatting and roles", () => {
  it("formats Colombian Spanish numbers and coordinates", () => {
    expect(fmtHa(14.91)).toBe("14,9 ha");
    expect(fmtHa(1234)).toBe("1.234 ha");
    expect(fmtCoord(-72.7894, 2.3944)).toBe("2.3944° N · 72.7894° O");
  });
  it("orders severities and checks role hierarchy", () => {
    expect(SEVERITY.priority.order).toBeGreaterThan(SEVERITY.high.order);
    expect(hasRole(user, "observer")).toBe(true);
    expect(hasRole(user, "admin")).toBe(false);
    expect(hasRole(null, "observer")).toBe(false);
  });
  it("builds repeated query params and skips empty values", () => {
    expect(buildQuery({ status: ["new", "in_review"], territory: "", page: 2, x: undefined })).toBe("?status=new&status=in_review&page=2");
  });
});

describe("validation mirrors backend rules", () => {
  it("rejects weak passwords, mismatches and missing privacy acceptance", () => {
    const r = registerSchema.safeParse({ full_name: "Ana", email: "ana@example.org", password: "corta", confirm: "otra", accept_privacy: false });
    expect(r.success).toBe(false);
    if (r.success) throw new Error("expected validation failure");
    const errors = zodErrors(r.error);
    expect(errors.password).toMatch(/12 caracteres/);
    expect(errors.accept_privacy).toMatch(/aceptar/);
  });
  it("rejects predictable passwords and HTML in names", () => {
    expect(registerSchema.safeParse({ full_name: "<b>x</b>", email: "a@b.co", password: "aaaaaaaaaaaaaa", confirm: "aaaaaaaaaaaaaa", accept_privacy: true }).success).toBe(false);
  });
  it("accepts a valid registration", () => {
    expect(registerSchema.safeParse({ full_name: "Ana Pérez", email: "ana@example.org", password: "selva-guaviare-26", confirm: "selva-guaviare-26", accept_privacy: true }).success).toBe(true);
    expect(loginSchema.safeParse({ email: "no-es-correo", password: "" }).success).toBe(false);
  });
});

describe("accessible components", () => {
  it("severity is conveyed by text and shape, not only colour", async () => {
    const { container } = render(<><SeverityBadge severity="priority" /><StatusBadge status="in_review" /></>);
    expect(screen.getByText("Hallazgo prioritario")).toBeInTheDocument();
    expect(screen.getByText("En revisión")).toBeInTheDocument();
    await expectNoAxeViolations(container);
  });

  it("text field wires label, hint and error to the input", async () => {
    const { container } = render(<TextField label="Correo" hint="Tu correo" error="Correo inválido" />);
    const input = screen.getByLabelText("Correo");
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(input.getAttribute("aria-describedby")).toBeTruthy();
    expect(screen.getByRole("alert")).toHaveTextContent("Correo inválido");
    await expectNoAxeViolations(container);
  });

  it("swipe comparison is operable with the keyboard", async () => {
    render(<SwipeCompare before="/a.jpg" after="/b.jpg" beforeLabel="ANTES" afterLabel="DESPUÉS" alt="Zona" />);
    const slider = screen.getByLabelText(/Deslizador de comparación/);
    expect(slider).toHaveValue("50");
    slider.focus();
    fireEvent.change(slider, { target: { value: "80" } });
    expect(slider).toHaveValue("80");
    expect(screen.getByAltText("Zona — ANTES")).toBeInTheDocument();
  });
});

describe("cookie consent (Ley 1581)", () => {
  it("shows the banner until a choice is made and never pre-checks optional categories", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("{}", { status: 201 }));
    render(<CookieBanner />);
    expect(await screen.findByRole("dialog", { name: /Tú decides/ })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Configurar preferencias" }));
    const functional = screen.getByRole("checkbox", { name: /Funcionales/ });
    const analytics = screen.getByRole("checkbox", { name: /Analíticas/ });
    expect(functional).not.toBeChecked();
    expect(analytics).not.toBeChecked();
    expect(screen.getByRole("checkbox", { name: /Necesarias/ })).toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: "Rechazar opcionales" }));
    const stored = JSON.parse(localStorage.getItem("fs_consent")!);
    expect(stored).toMatchObject({ functional: false, analytics: false, version: CONSENT_VERSION });
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/privacy/consent", expect.objectContaining({ method: "POST" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("functional storage is a no-op without consent", () => {
    act(() => useConsent.setState({ choice: null }));
    uiStorage.set("layers", { a: 1 });
    expect(localStorage.getItem("fs_ui")).toBeNull();
    act(() => useConsent.setState({ choice: { functional: true, analytics: false, version: CONSENT_VERSION, subject: "s", decided_at: "" } }));
    uiStorage.set("layers", { a: 1 });
    expect(uiStorage.get("layers", null)).toEqual({ a: 1 });
  });
});

describe("API client", () => {
  it("keeps the access token in memory and refreshes once for concurrent 401s", async () => {
    let refreshCalls = 0;
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/auth/refresh")) {
        refreshCalls++;
        return new Response(JSON.stringify({ access_token: "new-token", token_type: "bearer", expires_in: 900, user }), { status: 200 });
      }
      const auth = (init?.headers as Record<string, string>)?.Authorization;
      return auth === "Bearer new-token" ? new Response(JSON.stringify({ ok: true }), { status: 200 }) : new Response("{}", { status: 401 });
    });
    useAuth.setState({ status: "authenticated", accessToken: "expired", user });
    const results = await Promise.all([api("/alerts"), api("/regions"), api("/jobs")]);
    expect(results).toEqual([{ ok: true }, { ok: true }, { ok: true }]);
    expect(refreshCalls).toBe(1);
    expect(useAuth.getState().accessToken).toBe("new-token");
    expect(localStorage.length).toBe(0); // nunca se persiste
  });

  it("treats a 204 refresh as an anonymous visitor", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(null, { status: 204 }));
    expect(await refreshSession()).toBe(false);
    expect(useAuth.getState().status).toBe("anonymous");
  });

  it("maps the error envelope to ApiError with field details", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ error: { code: "validation_error", message: "Los datos enviados no son válidos.", details: [{ field: "email", message: "inválido" }] } }), { status: 422 }),
    );
    const err = (await api("/auth/register", { method: "POST", body: {}, auth: false }).catch((e: unknown) => e)) as ApiError;
    expect(err).toBeInstanceOf(ApiError);
    expect(err.code).toBe("validation_error");
    expect(err.details[0]?.field).toBe("email");
  });
});
