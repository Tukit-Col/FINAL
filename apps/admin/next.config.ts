import { join } from "node:path";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  transpilePackages: ["@tukit/contrato"],
  allowedDevOrigins: ["127.0.0.1"],
  outputFileTracingRoot: join(import.meta.dirname, "../.."),
  turbopack: {
    root: join(import.meta.dirname, "../.."),
  },
};

export default nextConfig;
