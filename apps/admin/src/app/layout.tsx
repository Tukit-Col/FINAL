import type { Metadata, Viewport } from "next";
import AvisoAcceso from "@/components/AvisoAcceso";
import CabeceraAdmin from "@/components/CabeceraAdmin";
import { tokenDeSesion } from "@/lib/sesion";
import "./globals.css";

export const metadata: Metadata = {
  title: "Tukit · Consola de revisión",
  description: "Revisión humana de los kits antes de publicarlos al acudiente (AD-01 a AD-07).",
  applicationName: "Tukit Admin",
  manifest: "/manifest.webmanifest",
  robots: { index: false, follow: false },
};

export const viewport: Viewport = {
  themeColor: "#0f172a",
  width: "device-width",
  initialScale: 1,
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const token = await tokenDeSesion();
  return (
    <html lang="es">
      <body suppressHydrationWarning>
        {token ? <CabeceraAdmin /> : null}
        <main>{token ? children : <AvisoAcceso motivo="sin_sesion" />}</main>
      </body>
    </html>
  );
}
