"use client";

import { usePathname } from "next/navigation";

import { NavLinks } from "@/components/layout/NavLinks";

/** Client wrapper: highlights the module that matches the current URL. */
export function ActiveNav() {
  const pathname = usePathname();
  return <NavLinks active={pathname.split("/")[1] || null} />;
}
