import Link from "next/link";

import { MODULES } from "@/domain/modules";

/** One instrument rail across all routes. */
export function NavLinks({ active }: { active: string | null }) {
  return (
    <nav className="nav" aria-label="Modules">
      {MODULES.filter((m) => m.inFlow).map((m) => (
        <NavItem key={m.slug} slug={m.slug} active={active === m.slug}>
          <span className="nav-label">{m.label}</span>
        </NavItem>
      ))}
    </nav>
  );
}

function NavItem({
  slug,
  active,
  children,
}: {
  slug: string;
  active: boolean;
  children: React.ReactNode;
}) {
  return (
    <Link
      href={`/${slug}`}
      className={`nav-item${active ? " nav-item-active" : ""}`}
      aria-current={active ? "page" : undefined}
    >
      {children}
    </Link>
  );
}
