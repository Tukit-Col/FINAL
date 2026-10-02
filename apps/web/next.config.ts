import { join } from "node:path";
import type { NextConfig } from "next";

// `@tukit/contrato` se publica como fuente TypeScript, no compilado: es un
// paquete del propio monorepo y compilarlo aparte solo agregaria un paso de
// build que hay que recordar correr. A cambio, Next tiene que transpilarlo.
const nextConfig: NextConfig = {
  transpilePackages: ["@tukit/contrato"],
  // Next 16 bloquea recursos de dev (HMR, chunks de cliente) si el host no es
  // localhost. En pruebas se entra por 127.0.0.1 / la IP de red; sin esto el JS
  // de cliente no carga (ni anima la linea de tiempo ni responden los chips).
  // `*.trycloudflare.com`: el tunel con que se prueba Wompi sandbox. Su
  // checkout rechaza volver a localhost o a una IP privada (403 en su CDN), asi
  // que la app se abre por el tunel y el retorno apunta ahi.
  allowedDevOrigins: ["127.0.0.1", "*.trycloudflare.com"],
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
