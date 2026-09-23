import { join } from "node:path";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  transpilePackages: ["@tukit/contrato"],
  // Next 16 bloquea recursos de dev (HMR, chunks de cliente) si el host no es
  // localhost. En pruebas se entra por 127.0.0.1 / la IP de red; sin esto el JS
  // de cliente no carga (ni anima la linea de tiempo ni responden los chips).
  allowedDevOrigins: ["127.0.0.1"],
  outputFileTracingRoot: join(import.meta.dirname, "../.."),
  turbopack: {
    root: join(import.meta.dirname, "../.."),
  },
};

export default nextConfig;
