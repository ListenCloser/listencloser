import type { Metadata } from "next";
import "./globals.css";
import "./workspace-v3.css";
import "./product-polish-v4.css";
import "./workspace-interactions.css";
import "./visual-language-v5.css";
import "./visual-language-v6.css";
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
