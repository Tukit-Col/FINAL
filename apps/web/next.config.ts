import { join } from "node:path";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  transpilePackages: ["@tukit/contrato"],
  allowedDevOrigins: ["127.0.0.1"],
  outputFileTracingRoot: join(import.meta.dirname, "../.."),
  turbopack: {
    root: join(import.meta.dirname, "../.."),
  },
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "**.exito.com" },
      { protocol: "https", hostname: "**.panamericana.com.co" },
      { protocol: "https", hostname: "**.pgrancentral.com" },
      { protocol: "https", hostname: "**.vtexassets.com" },
    ],
  },
};

export default nextConfig;
