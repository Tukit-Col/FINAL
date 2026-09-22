import { join } from "node:path";
import type { NextConfig } from "next";

// `@tukit/contrato` se publica como fuente TypeScript, no compilado: es un
// paquete del propio monorepo y compilarlo aparte solo agregaria un paso de
// build que hay que recordar correr. A cambio, Next tiene que transpilarlo.
const nextConfig: NextConfig = {
  transpilePackages: ["@tukit/contrato"],
  // La raiz del workspace, para que Next no adivine cual de los dos
  // `package.json` manda y no avise de lockfiles multiples.
  outputFileTracingRoot: join(import.meta.dirname, "../.."),
  turbopack: {
    root: join(import.meta.dirname, "../.."),
  },
  images: {
    // Las fotos del catalogo son las de las tiendas: se muestran desde su
    // origen, igual que hace `vista.py`. Sin red se cae al texto, que es lo
    // que de todos modos hay que leer.
    remotePatterns: [
      { protocol: "https", hostname: "**.exito.com" },
      { protocol: "https", hostname: "**.panamericana.com.co" },
      { protocol: "https", hostname: "**.pgrancentral.com" },
      { protocol: "https", hostname: "**.vtexassets.com" },
    ],
  },
};

export default nextConfig;
