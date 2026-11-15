import Link from "next/link";
import { Suspense, type ReactNode } from "react";

import { ActiveNav } from "@/components/layout/ActiveNav";
import { NavLinks } from "@/components/layout/NavLinks";

/** Shell of every working page: brand link to the landing page, module rail, footer. */
export default function WorkbenchLayout({ children }: { children: ReactNode }) {
  return (
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
  );
}
