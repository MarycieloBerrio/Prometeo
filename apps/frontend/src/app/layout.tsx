import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import { Suspense } from "react";

import { ActiveNav } from "@/components/layout/ActiveNav";
import { NavLinks } from "@/components/layout/NavLinks";
import "./globals.css";
import "./instrument.css";
import "./ignition.css";
import "./workbench.css";

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
        <div className="app-shell">
          <a className="skip-link" href="#main-content">Skip to content</a>
          <header className="topbar">
            <Link href="/" className="brand" aria-label="Prometeo home">PROMETEO<span className="brand-dot">.</span></Link>
            <Suspense fallback={<NavLinks active={null} />}>
              <ActiveNav />
            </Suspense>
          </header>
          <main className="main" id="main-content">{children}</main>
          <footer className="app-footer">
            <span>PROMETEO / MICROGRAVITY COMBUSTION</span>
            <span>Research support · not safety certification</span>
          </footer>
        </div>
      </body>
    </html>
  );
}
