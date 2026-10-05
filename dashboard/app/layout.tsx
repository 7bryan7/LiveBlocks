import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "LiveBlocks — Blockchain Analytics",
  description: "Explore Bitcoin address activity, fees, network trends, and data quality with Blockchain.com data.",
  other: {
    "codex-preview": "development",
  },
  icons: {
    icon: "/favicon.svg",
    shortcut: "/favicon.svg",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}
