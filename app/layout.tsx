import type { Metadata, Viewport } from "next";
import "./globals.css";
import "./workspace-v3.css";
import "./product-polish-v4.css";
import "./workspace-interactions.css";
// Keep visual-language layers last so product craft rules override structural chrome.
import "./visual-language-v5.css";
import "./visual-language-v6.css";
import "./mobile-workspace.css";
import { Geist } from "next/font/google";
import MSWInit from "@/components/MSWInit";
import AuthProvider from "@/components/AuthProvider";

const geist = Geist({ subsets: ["latin"], variable: "--font-sans" });

export const metadata: Metadata = {
  title: "Music Workspace",
  description: "Listen, transcribe, inspect, and analyze music.",
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
          <AuthProvider>{children}</AuthProvider>
        </MSWInit>
      </body>
    </html>
  );
}
