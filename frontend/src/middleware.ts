import { NextResponse, type NextRequest } from "next/server";

/**
 * Content Security Policy basada en nonce (Next.js toma el nonce del header de la
 * petición y lo aplica a sus propios scripts inline).
 * Los hosts externos se limitan a los proveedores abiertos de tiles de mapa/elevación.
 */
const TILE_HOSTS = [
  "https://tiles.openfreemap.org",
  "https://tiles.maps.eox.at",
  "https://s3.amazonaws.com",
  "https://elevation-tiles-prod.s3.amazonaws.com",
].join(" ");

export function middleware(request: NextRequest) {
  const nonce = btoa(crypto.randomUUID());
  const dev = process.env.NODE_ENV !== "production";
  const csp = [
    "default-src 'self'",
    `script-src 'self' 'nonce-${nonce}' 'strict-dynamic'${dev ? " 'unsafe-eval'" : ""}`,
    "style-src 'self' 'unsafe-inline'",
    `img-src 'self' blob: data: ${TILE_HOSTS}`,
    `connect-src 'self' ${TILE_HOSTS}${dev ? " ws:" : ""}`,
    "font-src 'self'",
    "worker-src 'self' blob:",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
    ...(dev ? [] : ["upgrade-insecure-requests"]),
  ].join("; ");

  const headers = new Headers(request.headers);
  headers.set("x-nonce", nonce);
  headers.set("Content-Security-Policy", csp);
  const response = NextResponse.next({ request: { headers } });
  response.headers.set("Content-Security-Policy", csp);
  return response;
}

export const config = {
  matcher: [
    {
      source: "/((?!api|_next/static|_next/image|textures|story|data|favicon.ico).*)",
      missing: [
        { type: "header", key: "next-router-prefetch" },
        { type: "header", key: "purpose", value: "prefetch" },
      ],
    },
  ],
};
