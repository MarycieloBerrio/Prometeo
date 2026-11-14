import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";

import { MODULES } from "@/domain/modules";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Prometeo — Scientific Intelligence for Fire Safety in Space",
  description:
    "Evidence-grounded exploration of NASA microgravity combustion experiments (BASS-II, FLEX, SAFFIRE).",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable}`}>
      <body>
        <header className="topbar">
          <Link href="/" className="brand">
            PROMETEO
          </Link>
          <nav>
            {MODULES.map((m) => (
              <Link key={m.slug} href={`/${m.slug}`}>
                {m.name}
              </Link>
            ))}
          </nav>
        </header>
        <main className="container">{children}</main>
      </body>
    </html>
  );
}
