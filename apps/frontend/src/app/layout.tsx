import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";

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

/**
 * Document shell only. The landing page and the working pages each render their own
 * `.app-shell`: Next keeps the previous route in the DOM (hidden) after a client navigation,
 * so one shared shell styled by "which page is inside" would keep the landing page's rules
 * (no top bar, no padding) on every page reached from it.
 */
export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable}`}>
      <body>{children}</body>
    </html>
  );
}
