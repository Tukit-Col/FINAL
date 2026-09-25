import type { Metadata, Viewport } from "next";
import CabeceraAdmin from "@/components/CabeceraAdmin";
import "./globals.css";

export const metadata: Metadata = {
  title: "Tukit · Consola de revisión",
  description: "Revisión humana de los kits antes de publicarlos al acudiente (AD-01 a AD-07).",
  applicationName: "Tukit Admin",
  // Una consola interna no se indexa: no tiene nada que hacer en un buscador.
  robots: { index: false, follow: false },
};

export const viewport: Viewport = {
  themeColor: "#0f172a",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es">
      {/* Extensiones del navegador (ColorZilla, gestores de atajos) inyectan
          atributos como `cz-shortcut-listen` en <body> tras el SSR y disparan
          un aviso de hidratación que no es nuestro. Silenciarlo solo en <body>. */}
      <body suppressHydrationWarning>
        <CabeceraAdmin />
        <main>{children}</main>
      </body>
    </html>
  );
}
