import type { ReactNode } from "react";

import { Icon, type IconName } from "@/components/ui/Icon";

/** One register of an answer's basis. Starts open: the basis should not need a click. */
export function Group({
  icon,
  title,
  count,
  children,
}: {
  icon: IconName;
  title: string;
  count: number;
  children: ReactNode;
}) {
  return (
    <details className={`group${count === 0 ? " group-empty" : ""}`} open>
      <summary>
        <Icon name={icon} size={16} />
        <span>{title}</span>
        <span className="count">{count}</span>
      </summary>
      <div className="group-body">{count > 0 ? children : <p className="small muted">No entries returned in this register.</p>}</div>
    </details>
  );
}
