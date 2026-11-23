import type { Metadata, Viewport } from "next";
import { IBM_Plex_Mono, Newsreader, Public_Sans } from "next/font/google";
import { headers } from "next/headers";
import type { ReactNode } from "react";
import "maplibre-gl/dist/maplibre-gl.css";
import "./globals.css";
import { Providers } from "./providers";

// «Atlas de campo»: una serif de periódico con tamaños ópticos para los títulos, una grotesca cívica
// para la lectura, y una mono técnica para coordenadas, códigos y fechas.
const display = Newsreader({ subsets: ["latin"], style: ["normal", "italic"], axes: ["opsz"], variable: "--font-newsreader", display: "swap" });
const sans = Public_Sans({ subsets: ["latin"], variable: "--font-public-sans", display: "swap" });
const mono = IBM_Plex_Mono({ subsets: ["latin"], weight: ["400", "500"], variable: "--font-plex-mono", display: "swap" });

export const metadata: Metadata = {
  title: { default: "Forest Sentinel — Vigilancia temprana de bosques", template: "%s · Forest Sentinel" },
  description:
    "Plataforma de detección temprana de cambios en la cobertura forestal con imágenes Sentinel-2 en Guaviare, Sierra Nevada de Santa Marta, Cundinamarca y Amazonas.",
  robots: { index: true, follow: true },
};

export const viewport: Viewport = { themeColor: "#f4f2eb", colorScheme: "light" };

export default async function RootLayout({ children }: { children: ReactNode }) {
  // Leer el nonce hace que las páginas se rendericen dinámicamente, y así aplican los nonces de la CSP.
  await headers();
  return (
    <html lang="es-CO" className={`${display.variable} ${sans.variable} ${mono.variable}`}>
      <body>
        <a href="#contenido" className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[200] focus:rounded-xs focus:bg-ink focus:px-4 focus:py-2 focus:text-paper">
          Saltar al contenido
        </a>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
