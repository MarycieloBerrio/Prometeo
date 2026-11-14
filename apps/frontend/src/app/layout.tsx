import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import { Suspense } from "react";

import { ActiveNav } from "@/components/layout/ActiveNav";
import { NavLinks } from "@/components/layout/NavLinks";
import { Icon } from "@/components/ui/Icon";
import { ThermalField } from "@/components/ui/ThermalField";
import "./globals.css";
import "./instrument.css";

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
          <ThermalField />
          <a className="skip-link" href="#main-content">Skip to content</a>
          <header className="topbar">
            <Link href="/" className="brand" aria-label="Prometeo home">
              <span className="brand-mark"><Icon name="flame" size={24} /></span>
              <span className="brand-name">PROMETEO<small>MICROGRAVITY EVIDENCE LAB</small></span>
            </Link>
            <Suspense fallback={<NavLinks active={null} />}>
              <ActiveNav />
            </Suspense>
            <div className="topbar-status" title="Research support, not certification">
              <span className="status-led" />
              <span>RESEARCH MODE</span>
            </div>
          </header>
          <main className="main" id="main-content">{children}</main>
          <footer className="app-footer">
            <span>PROMETEO / EVIDENCE WORKSPACE</span>
            <span><Icon name="shield" size={14} /> Research support · not safety certification</span>
          </footer>
        </div>
      </body>
    </html>
  );
}
