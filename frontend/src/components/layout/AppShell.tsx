"use client";

import { AnimatePresence, motion } from "framer-motion";
import { Activity, Bell, BookOpen, FileText, Globe2, LayoutGrid, LogOut, Map, MoreHorizontal, Settings, ShieldAlert, Users, X } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { LogoMark } from "@/components/brand/Logo";
import { api } from "@/lib/api/client";
import { useOverview } from "@/lib/api/hooks";
import { hasRole, useAuth } from "@/lib/auth/store";
import { cn } from "@/lib/cn";
import { project } from "@/lib/motion";
import { ROLE, fmtRelative } from "@/lib/format";

interface NavItem {
  href: string;
  label: string;
  icon: typeof Map;
  admin?: boolean;
}

const PRIMARY: NavItem[] = [
  { href: "/app", label: "Centro", icon: LayoutGrid },
  { href: "/app/explorer", label: "Explorador", icon: Map },
  { href: "/app/alerts", label: "Alertas", icon: ShieldAlert },
  { href: "/app/regions", label: "Zonas", icon: Globe2 },
];

const SECONDARY: NavItem[] = [
  { href: "/app/jobs", label: "Análisis", icon: Activity },
  { href: "/app/reports", label: "Reportes", icon: FileText },
  { href: "/app/notifications", label: "Notificaciones", icon: Bell },
  { href: "/app/users", label: "Usuarios", icon: Users, admin: true },
  { href: "/app/settings", label: "Configuración", icon: Settings },
  { href: "/help", label: "Ayuda", icon: BookOpen },
];

function isActive(pathname: string, href: string) {
  return href === "/app" ? pathname === "/app" : pathname.startsWith(href);
}

function RailLink({ item, pathname, badge }: { item: NavItem; pathname: string; badge?: number }) {
  const active = isActive(pathname, item.href);
  const Icon = item.icon;
  return (
    <Link
      href={item.href}
      aria-current={active ? "page" : undefined}
      className={cn(
        "group relative flex min-h-11 items-center gap-3 px-3 py-2 text-sm transition-colors duration-200",
        active ? "font-semibold text-ink" : "text-ink-2 hover:bg-paper-2 hover:text-ink",
      )}
    >
      {active && <motion.span layoutId="rail-active" className="absolute inset-y-1.5 left-0 w-[3px] bg-ink" />}
      <Icon className={cn("size-[18px] shrink-0 transition-colors", active ? "text-brand" : "text-ink-3")} strokeWidth={1.6} aria-hidden />
      <span>{item.label}</span>
      {!!badge && <span className="ml-auto font-mono text-xs font-medium text-ochre">{badge}</span>}
    </Link>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const { status, user, clear } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const [moreOpen, setMoreOpen] = useState(false);
  const { data: overview } = useOverview();

  useEffect(() => {
    if (status === "anonymous") router.replace(`/login?next=${encodeURIComponent(pathname)}`);
  }, [status, router, pathname]);
  useEffect(() => setMoreOpen(false), [pathname]);

  async function logout() {
    await api("/auth/logout", { method: "POST" }).catch(() => undefined);
    clear();
    router.replace("/");
  }

  if (status !== "authenticated" || !user) {
    return (
      <div className="grid min-h-[100svh] place-items-center" role="status" aria-live="polite">
        <div className="flex flex-col items-center gap-4">
          <LogoMark className="size-14 motion-safe:animate-pulse" />
          <p className="eyebrow">VERIFICANDO SESIÓN…</p>
        </div>
      </div>
    );
  }

  const secondary = SECONDARY.filter((i) => !i.admin || hasRole(user, "admin"));

  return (
    <div className="min-h-[100svh] lg:grid lg:grid-cols-[248px_minmax(0,1fr)]">
      {/* Riel de instrumentos en escritorio */}
      <aside className="sticky top-0 hidden h-[100svh] flex-col border-r border-ink bg-paper-2 px-4 py-5 lg:flex">
        <Link href="/" className="flex items-center gap-2.5 px-2" aria-label="Forest Sentinel, portada">
          <LogoMark />
          <span className="font-display text-[1.375rem] font-semibold tracking-[-0.01em] text-ink">Forest Sentinel</span>
        </Link>
        <nav aria-label="Secciones" className="mt-8 flex flex-1 flex-col gap-6 overflow-y-auto">
          <div className="flex flex-col gap-1">
            <p className="eyebrow border-b border-rule px-3 pb-2 mb-1">OPERACIÓN</p>
            {PRIMARY.map((item) => (
              <RailLink key={item.href} item={item} pathname={pathname} badge={item.href === "/app/alerts" ? overview?.alerts_pending : undefined} />
            ))}
          </div>
          <div className="flex flex-col gap-1">
            <p className="eyebrow border-b border-rule px-3 pb-2 mb-1">GESTIÓN</p>
            {secondary.map((item) => (
              <RailLink key={item.href} item={item} pathname={pathname} />
            ))}
          </div>
        </nav>
        <div className="mt-4 border-t border-rule px-3 pt-3">
          <div className="flex items-center gap-2 text-xs font-semibold tracking-[0.04em] text-ink">
            <span className={cn("size-2", overview?.jobs_running ? "bg-brand motion-safe:animate-pulse" : "bg-ink-3")} />
            {overview?.jobs_running ? `${overview.jobs_running} ANÁLISIS EN CURSO` : "SISTEMA EN ESPERA"}
          </div>
          <p className="mt-1 text-xs text-ink-2">Última actualización {fmtRelative(overview?.last_update)}</p>
        </div>
        <div className="mt-3 flex items-center gap-3 border-t border-rule px-1 pt-3">
          <div className="grid size-9 place-items-center rounded-xs border border-ink font-display text-lg font-semibold text-ink" aria-hidden>
            {user.full_name.slice(0, 1).toUpperCase()}
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm text-ink">{user.full_name}</p>
            <p className="text-xs text-ink-2">{ROLE[user.role]}</p>
          </div>
          <button onClick={logout} className="grid size-11 place-items-center rounded-xs text-ink-2 hover:bg-paper-3 hover:text-ink" aria-label="Cerrar sesión" title="Cerrar sesión">
            <LogOut className="size-4" />
          </button>
        </div>
      </aside>

      {/* Barra superior en móvil */}
      <header className="sticky top-0 z-40 flex h-14 items-center justify-between border-b border-ink bg-paper px-4 lg:hidden">
        <Link href="/app" className="flex items-center gap-2" aria-label="Centro de operaciones">
          <LogoMark className="size-7" />
          <span className="font-display text-lg font-semibold">Forest Sentinel</span>
        </Link>
        <span className="eyebrow">{ROLE[user.role]?.toUpperCase()}</span>
      </header>

      <main id="contenido" className="min-w-0 pb-24 lg:pb-0">
        {children}
      </main>

      {/* Barra de pestañas inferior en móvil — composición propia, al alcance del pulgar */}
      <nav aria-label="Secciones" className="fixed inset-x-0 bottom-0 z-40 border-t border-ink bg-paper pb-[env(safe-area-inset-bottom)] lg:hidden">
        <ul className="grid grid-cols-5">
          {PRIMARY.map((item) => {
            const active = isActive(pathname, item.href);
            const Icon = item.icon;
            return (
              <li key={item.href}>
                <Link href={item.href} aria-current={active ? "page" : undefined} className={cn("relative flex h-16 flex-col items-center justify-center gap-1 text-[0.6875rem]", active ? "font-semibold text-ink before:absolute before:inset-x-3 before:top-0 before:h-[3px] before:bg-ink" : "text-ink-2")}>
                  <Icon className="size-5" aria-hidden />
                  {item.label}
                </Link>
              </li>
            );
          })}
          <li>
            <button onClick={() => setMoreOpen(true)} className="flex h-16 w-full flex-col items-center justify-center gap-1 text-[0.6875rem] text-ink-2" aria-expanded={moreOpen} aria-controls="more-sheet">
              <MoreHorizontal className="size-5" aria-hidden />
              Más
            </button>
          </li>
        </ul>
      </nav>
      <AnimatePresence>
        {moreOpen && (
          <>
            <motion.div className="fixed inset-0 z-40 bg-ink/40 lg:hidden" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={() => setMoreOpen(false)} />
            <motion.div
              id="more-sheet"
              role="dialog"
              aria-label="Más secciones"
              className="fixed inset-x-0 bottom-0 z-50 touch-none border-t border-ink bg-paper p-4 pt-2 pb-[max(1rem,env(safe-area-inset-bottom))] shadow-float lg:hidden"
              // Entra desde el borde inferior y se cierra hacia ahí mismo (mismo camino de ida y vuelta).
              initial={{ y: "100%", opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              exit={{ y: "100%", opacity: 0 }}
              // Gesto del sheet: sigue al dedo 1:1, hace efecto de liga hacia arriba, y un flick
              // (momentum proyectado) o arrastrarlo más de un tercio de su altura lo cierra.
              drag="y"
              dragConstraints={{ top: 0, bottom: 0 }}
              dragElastic={{ top: 0.08, bottom: 1 }}
              dragMomentum={false}
              dragTransition={{ bounceStiffness: 400, bounceDamping: 32 }}
              onDragEnd={(e, info) => {
                const height = (e.target as HTMLElement | null)?.closest?.("#more-sheet")?.getBoundingClientRect().height ?? 240;
                if (info.offset.y + project(info.velocity.y) > height / 3) setMoreOpen(false);
              }}
            >
              <div aria-hidden className="mx-auto mb-2 h-1 w-10 bg-ink-3" />
              <div className="mb-2 flex items-center justify-between">
                <p className="eyebrow">Más secciones</p>
                <button onClick={() => setMoreOpen(false)} aria-label="Cerrar" className="grid size-11 place-items-center rounded-xs text-ink-2">
                  <X className="size-5" />
                </button>
              </div>
              <div className="grid grid-cols-2 gap-1">
                {secondary.map((item) => (
                  <RailLink key={item.href} item={item} pathname={pathname} />
                ))}
                <button onClick={logout} className="flex min-h-11 items-center gap-3 px-3 py-2 text-sm text-ink-2">
                  <LogOut className="size-[18px]" /> Cerrar sesión
                </button>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </div>
  );
}

export function PageHeader({ eyebrow, title, description, actions }: { eyebrow: string; title: ReactNode; description?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mx-5 flex flex-col gap-4 border-b border-ink pt-8 pb-6 mb-8 sm:mx-8 md:flex-row md:items-end md:justify-between lg:pt-12">
      <div className="max-w-3xl">
        <p className="eyebrow mb-3">{eyebrow}</p>
        <h1 className="font-display display-tight text-[clamp(2.25rem,4vw,3.052rem)] leading-[1.04] font-medium text-ink">{title}</h1>
        {description && <p className="mt-3 max-w-[62ch] text-ink-2">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}
