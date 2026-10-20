import type { NextConfig } from "next";

const backend = process.env.BACKEND_URL ?? "http://localhost:8000";

const securityHeaders = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
];

const nextConfig: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  // Obraz Dockera używa samodzielnego serwera; lokalnie wystarcza `next start`.
  output: process.env.NEXT_OUTPUT === "standalone" ? "standalone" : undefined,
  // Publiczne API backendu pod tym samym adresem co aplikacja (jedno publiczne API, trwałe adresy).
  async rewrites() {
    return [{ source: "/api/v1/:path*", destination: `${backend}/api/v1/:path*` }];
  },
  async headers() {
    return [
      { source: "/:path*", headers: securityHeaders },
      // Service worker zawsze świeży — inaczej przeglądarka mogłaby trzymać starą logikę pamięci podręcznej.
      { source: "/sw.js", headers: [{ key: "Cache-Control", value: "no-cache" }] },
    ];
  },
};

export default nextConfig;
