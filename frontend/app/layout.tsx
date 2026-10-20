import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";

import { DemoBanner } from "@/components/site/DemoBanner";
import { ServiceWorker } from "@/components/site/ServiceWorker";
import { SiteFooter } from "@/components/site/SiteFooter";
import { SiteHeader } from "@/components/site/SiteHeader";
import { getMode } from "@/lib/mode";

import "./globals.css";

export const metadata: Metadata = {
  metadataBase: new URL(process.env.SITE_URL ?? "http://localhost:3000"),
  title: { default: "Przepisy budowlane w jednym miejscu", template: "%s · Przepisy budowlane" },
  description:
    "Oficjalny tekst przepisów budowlanych z jawnym typem i datą aktualności oraz objaśnienie prostym językiem. Dla inwestorów i urzędników.",
  applicationName: "Przepisy budowlane",
  manifest: "/manifest.webmanifest",
  icons: {
    icon: [
      { url: "/favicon.svg", type: "image/svg+xml" },
      { url: "/icons/favicon-32.png", sizes: "32x32", type: "image/png" },
      { url: "/icons/favicon-16.png", sizes: "16x16", type: "image/png" },
    ],
    apple: "/icons/apple-touch-icon.png",
  },
  openGraph: {
    type: "website",
    locale: "pl_PL",
    siteName: "Przepisy budowlane",
    images: [{ url: "/icons/og-image-1200x630.png", width: 1200, height: 630, alt: "Przepisy budowlane w jednym miejscu" }],
  },
  formatDetection: { telephone: false },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f6f4ef" },
    { media: "(prefers-color-scheme: dark)", color: "#12161d" },
  ],
};

export default async function RootLayout({ children }: { children: ReactNode }) {
  const mode = await getMode();
  return (
    <html lang="pl">
      <body className={mode === "expert" ? "pb-expert-page" : "pb-simple-page"}>
        <a className="pb-skip" href="#tresc">
          Przejdź do treści
        </a>
        <SiteHeader mode={mode} />
        <DemoBanner />
        <main id="tresc" tabIndex={-1}>
          <div className="pb-wrap">{children}</div>
        </main>
        <SiteFooter />
        <ServiceWorker />
      </body>
    </html>
  );
}
