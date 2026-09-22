import type { Metadata, Viewport } from "next";
import { descripcionOrigen } from "@tukit/contrato/servidor";
import CabeceraAdmin from "@/components/CabeceraAdmin";
import CintaOrigen from "@/components/CintaOrigen";
import "./globals.css";

export const metadata: Metadata = {
  title: "Tukit · Consola de revisión",
  description: "Revisión humana de los kits antes de publicarlos al acudiente (AD-02 a AD-07).",
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
  // El origen se resuelve en el servidor y se pinta arriba. En esta app la
  // cinta no es una ayuda de depuracion: aprobar un trabajo del almacen
  // simulado creyendo que es el backend real es el error caro de la pantalla.
  const origen = descripcionOrigen();

  return (
    <html lang="es">
      <body>
        <CintaOrigen nombre={origen.nombre} detalle={origen.detalle} />
        <CabeceraAdmin />
        <main>{children}</main>
      </body>
    </html>
  );
}
