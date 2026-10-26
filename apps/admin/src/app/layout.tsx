import type { Metadata, Viewport } from "next";
import AvisoAcceso from "@/components/AvisoAcceso";
import CabeceraAdmin from "@/components/CabeceraAdmin";
import { tokenDeSesion } from "@/lib/sesion";
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

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  // Sin cookie no hay nada que mostrar: el gateway corta /v1/admin con 401 y
  // cada pagina lo pintaba a su manera (un 500, o "revisa que el servicio este
  // arriba" con "Cerrar sesion" en la cabecera). Un solo aviso, antes de leer.
  // El token no se valida aqui; si vencio, cada pagina lo dice con su aviso.
  const token = await tokenDeSesion();
  return (
    <html lang="es">
      {/* Extensiones del navegador (ColorZilla, gestores de atajos) inyectan
          atributos como `cz-shortcut-listen` en <body> tras el SSR y disparan
          un aviso de hidratación que no es nuestro. Silenciarlo solo en <body>. */}
      <body suppressHydrationWarning>
        {token ? <CabeceraAdmin /> : null}
        <main>{token ? children : <AvisoAcceso motivo="sin_sesion" />}</main>
      </body>
    </html>
  );
}
