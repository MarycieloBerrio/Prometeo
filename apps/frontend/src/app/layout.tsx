import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import { Suspense } from "react";

import { ActiveNav } from "@/components/layout/ActiveNav";
import { NavLinks } from "@/components/layout/NavLinks";
import { Icon } from "@/components/ui/Icon";
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
        <div className="shell">
          <aside className="sidebar">
            <Link href="/" className="brand">
              <Icon name="flame" size={22} />
              <span>PROMETEO</span>
            </Link>
            <Suspense fallback={<NavLinks active={null} />}>
              <ActiveNav />
            </Suspense>
            <p className="sidebar-note">
              <Icon name="shield" size={14} />
              <span>Research tool. Not a safety certification.</span>
            </p>
          </aside>
          <main className="main">{children}</main>
        </div>
      </body>
    </html>
  );
}
