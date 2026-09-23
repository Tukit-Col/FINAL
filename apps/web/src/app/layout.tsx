import type { Metadata, Viewport } from "next";
import { descripcionOrigen } from "@tukit/contrato/servidor";
import Cabecera from "@/components/Cabecera";
import CintaOrigen from "@/components/CintaOrigen";
import "./globals.css";

export const metadata: Metadata = {
  title: "Tukit — la lista del colegio, resuelta",
  description:
    "Sube la lista de utiles de tu colegio y te armamos tres kits, con los libros y lo que de verdad hay disponible.",
  applicationName: "Tukit",
  manifest: "/manifest.webmanifest",
};

export const viewport: Viewport = {
  themeColor: "#2563eb",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  // El origen se resuelve en el servidor y se pinta arriba. Que la pantalla
  // diga si esta mirando datos simulados o el backend real evita la peor
  // confusion posible de esta etapa: creer que algo funciona porque se ve.
  const origen = descripcionOrigen();

  return (
    <html lang="es">
      {/* Extensiones del navegador (p. ej. ColorZilla) inyectan atributos como
          `cz-shortcut-listen` en el <body> antes de que React hidrate, lo que
          dispara un aviso de hidratación por algo que no controlamos. Suprimirlo
          solo en este nodo evita el falso positivo sin ocultar otros. */}
      <body suppressHydrationWarning>
        <CintaOrigen nombre={origen.nombre} detalle={origen.detalle} />
        <Cabecera />
        <main>{children}</main>
      </body>
    </html>
  );
}
