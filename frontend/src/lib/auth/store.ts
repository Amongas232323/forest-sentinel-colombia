"use client";

import { create } from "zustand";
import type { Role, User } from "@/lib/api/types";

/**
 * El access token vive SOLO en memoria (nunca en localStorage) para que un XSS no pueda
 * leer una credencial de larga duración. El refresh token es una cookie httpOnly.
 */
type Status = "unknown" | "authenticated" | "anonymous";

interface AuthState {
  status: Status;
  accessToken: string | null;
  user: User | null;
  setSession: (token: string, user: User) => void;
  clear: () => void;
}

export const useAuth = create<AuthState>((set) => ({
  status: "unknown",
  accessToken: null,
  user: null,
  setSession: (accessToken, user) => set({ accessToken, user, status: "authenticated" }),
  clear: () => set({ accessToken: null, user: null, status: "anonymous" }),
}));

const RANK: Record<Role, number> = { observer: 0, analyst: 1, admin: 2 };

export function hasRole(user: User | null, minimum: Role): boolean {
  return !!user && RANK[user.role] >= RANK[minimum];
}
