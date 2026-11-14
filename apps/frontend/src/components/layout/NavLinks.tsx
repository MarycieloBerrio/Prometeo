import Link from "next/link";

import { Icon } from "@/components/ui/Icon";
import { MODULES } from "@/domain/modules";

/** Sidebar links. `active` is the current first path segment, or null when unknown. */
export function NavLinks({ active }: { active: string | null }) {
  const flow = MODULES.filter((m) => m.inFlow);
  const later = MODULES.filter((m) => !m.inFlow);
  return (
    <nav className="nav" aria-label="Modules">
      <p className="nav-title">Workflow</p>
      {flow.map((m) => (
        <NavItem key={m.slug} slug={m.slug} active={active === m.slug}>
          <span className="nav-step">{Number(m.number)}</span>
          <Icon name={m.icon} />
          <span className="nav-label">{m.label}</span>
        </NavItem>
      ))}
      <p className="nav-title">Later</p>
      {later.map((m) => (
        <NavItem key={m.slug} slug={m.slug} active={active === m.slug}>
          <span className="nav-step" />
          <Icon name={m.icon} />
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
