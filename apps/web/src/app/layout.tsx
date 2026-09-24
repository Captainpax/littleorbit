import type { Metadata, Viewport } from "next";
import "@once-ui-system/core/css/styles.css";
import "./styles.css";
import { Providers } from "./providers";
import { SiteFooter } from "@/components/site-footer";
import { SiteHeader } from "@/components/site-header";

export const metadata: Metadata = {
  metadataBase: new URL(process.env.NEXT_PUBLIC_BASE_URL ?? "http://localhost:3000"),
  title: { default: "Little Orbit — Closer, every day", template: "%s · Little Orbit" },
  description: "A free and open couples app for daily questions, shared notes, countdowns, and time together.",
  openGraph: {
    title: "Little Orbit",
    description: "A private place for two. Free for everyone, with no paywalls.",
    type: "website",
  },
  alternates: { types: { "application/rss+xml": "/patch-notes.xml" } },
};

export const viewport: Viewport = { themeColor: "#10172b", colorScheme: "dark" };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" data-scroll-behavior="smooth" suppressHydrationWarning>
      <body>
        <Providers>
          <a className="skip-link" href="#main">Skip to content</a>
          <SiteHeader />
          {children}
          <SiteFooter />
        </Providers>
      </body>
    </html>
  );
}
