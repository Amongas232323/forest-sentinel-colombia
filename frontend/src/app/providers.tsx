"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MotionConfig } from "framer-motion";
import { useEffect, useState, type ReactNode } from "react";
import { Toaster } from "@/components/ui/Feedback";
import { refreshSession } from "@/lib/api/client";
import { ApiError } from "@/lib/api/client";
import { useAuth } from "@/lib/auth/store";
import { SPRING } from "@/lib/motion";
import { CookieBanner } from "@/features/privacy/CookieBanner";

function AuthBootstrap() {
  const status = useAuth((s) => s.status);
  useEffect(() => {
    // Recuperamos la sesión desde la cookie httpOnly de refresh (si existe).
    if (status === "unknown") void refreshSession();
  }, [status]);
  return null;
}

export function Providers({ children }: { children: ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 15_000,
            refetchOnWindowFocus: false,
            retry: (count, err) => !(err instanceof ApiError && err.status < 500) && count < 2,
          },
        },
      }),
  );
  return (
    // reducedMotion="user": con prefers-reduced-motion, Framer quita las animaciones de transform
    // y deja las de opacidad (fundidos). SPRING reemplaza el resorte por defecto de Framer,
    // que es subamortiguado (ζ≈0.56), para que nada rebote si no hay un gesto detrás.
    <MotionConfig reducedMotion="user" transition={SPRING}>
    <QueryClientProvider client={client}>
      <AuthBootstrap />
      {children}
      <Toaster />
      <CookieBanner />
    </QueryClientProvider>
    </MotionConfig>
  );
}
