import type { Metadata, Viewport } from "next";
import Cabecera from "@/components/Cabecera";
import PieDelSitio from "@/components/PieDelSitio";
import "./globals.css";

export const metadata: Metadata = {
  title: "Tukit — la lista del colegio, resuelta",
  description:
    "Sube la lista de utiles de tu colegio y te armamos tres kits, con los libros y lo que de verdad hay disponible.",
  applicationName: "Tukit",
  manifest: "/manifest.webmanifest",
  // Los iconos (icon.png, apple-icon.png, favicon.ico) y la imagen para
  // compartir (opengraph-image.tsx) los toma Next de los archivos de esta
  // carpeta; aqui solo va el texto de la tarjeta al compartir el enlace.
  openGraph: {
    title: "Tukit — la lista del colegio, resuelta",
    description:
      "Sube la lista de utiles de tu colegio y te armamos tres kits, en un solo pedido.",
    siteName: "Tukit",
    locale: "es_CO",
    type: "website",
  },
  twitter: { card: "summary_large_image" },
};

export const viewport: Viewport = {
  themeColor: "#2563eb",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es">
      {/* Extensiones del navegador (p. ej. ColorZilla) inyectan atributos como
          `cz-shortcut-listen` en el <body> antes de que React hidrate, lo que
          dispara un aviso de hidratación por algo que no controlamos. Suprimirlo
          solo en este nodo evita el falso positivo sin ocultar otros. */}
      <body suppressHydrationWarning>
        <Cabecera />
        <main>{children}</main>
        <PieDelSitio />
      </body>
    </html>
  );
}
