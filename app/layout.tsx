import type { Metadata, Viewport } from "next";
import "./globals.css";
import "./product-polish-v4.css";
import "./visual-language.css";
import "./representation-visuals.css";
import "./breakdown.css";
import "./landing-product-story.css";
// Canonical UI tokens load after historical layers so their variables resolve
// consistently while #523 retires those styles. The remaining narrow bridge
// follows the token contract; structural phone/touch invariants load last.
import "./tokens.css";
import "./interface-foundation.css";
import "./mobile-workspace.css";
import { Geist } from "next/font/google";
import MSWInit from "@/components/MSWInit";
import AuthProvider from "@/components/AuthProvider";
import QueryProvider from "@/components/QueryProvider";

const geist = Geist({ subsets: ["latin"], variable: "--font-sans" });

export const metadata: Metadata = {
  title: "Listen Closer",
  description: "Move through a recording, musical representations, and evidence-backed analysis without losing your place.",
  icons: {
    icon: "/icon.svg",
    apple: "/icon.svg",
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`font-sans ${geist.variable}`}>
      <body>
        <MSWInit>
          <QueryProvider>
            <AuthProvider>{children}</AuthProvider>
          </QueryProvider>
        </MSWInit>
      </body>
    </html>
  );
}
