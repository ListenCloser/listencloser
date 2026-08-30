import type { Metadata, Viewport } from "next";
import "./globals.css";
import "./workspace-v3.css";
import "./product-polish-v4.css";
import "./workspace-interactions.css";
// Keep visual-language rules after structural chrome so product craft wins the cascade.
import "./visual-language.css";
import "./mobile-workspace.css";
import "./readiness-polish-v6.css";
import "./breakdown.css";
// Signed-out only: product-native landing story without changing workspace chrome.
import "./landing-product-story.css";
import { Geist } from "next/font/google";
import MSWInit from "@/components/MSWInit";
import AuthProvider from "@/components/AuthProvider";
import QueryProvider from "@/components/QueryProvider";

const geist = Geist({ subsets: ["latin"], variable: "--font-sans" });

export const metadata: Metadata = {
  title: "Music Workspace",
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

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
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
