import type { NextConfig } from "next";

const BACKEND = process.env.SLIDEX_BACKEND_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  // Compression buffers Server-Sent Events through the proxy; this is a local-only app.
  compress: false,
  // The browser only ever talks to /api on this origin; the OpenAI key stays in the backend.
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${BACKEND}/:path*` }];
  },
  // SSE and large uploads pass straight through the proxy.
  experimental: {
    proxyTimeout: 30 * 60 * 1000,
  },
};

export default nextConfig;
