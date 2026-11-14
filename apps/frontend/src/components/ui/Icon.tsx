import type { ReactNode } from "react";

/** Small inline icon set (24×24, stroke = currentColor). No icon dependency, works offline. */
const PATHS = {
  flame: (
    <path d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.153.433-2.294 1-3a2.5 2.5 0 0 0 2.5 2.5z" />
  ),
  search: (
    <>
      <circle cx="11" cy="11" r="7" />
      <path d="m21 21-4.3-4.3" />
    </>
  ),
  compare: <path d="M8 3 4 7l4 4M4 7h16M16 21l4-4-4-4M20 17H4" />,
  video: (
    <>
      <rect x="2" y="6" width="14" height="12" rx="2" />
      <path d="m16 10 6-3v10l-6-3" />
    </>
  ),
  chat: <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />,
  rocket: (
    <>
      <path d="M12 2c3 2.5 4.5 6 4.5 10v4h-9v-4C7.5 8 9 4.5 12 2z" />
      <path d="M7.5 13 5 16v3l2.5-1.5M16.5 13l2.5 3v3l-2.5-1.5M10 20h4" />
      <circle cx="12" cy="9" r="1.5" />
    </>
  ),
  wind: (
    <path d="M3 8h10a3 3 0 1 0-3-3M3 12h15a3 3 0 1 1-3 3M3 16h7a2.5 2.5 0 1 1-2.5 2.5" />
  ),
  oxygen: (
    <>
      <circle cx="8.5" cy="12" r="4.5" />
      <circle cx="15.5" cy="12" r="4.5" />
    </>
  ),
  layers: <path d="m12 3 9 5-9 5-9-5 9-5zM3 13l9 5 9-5" />,
  box: <path d="M21 8 12 3 3 8v8l9 5 9-5V8zM3 8l9 5 9-5M12 13v8" />,
  gauge: (
    <>
      <path d="M4 18a9 9 0 1 1 16 0" />
      <path d="m12 14 4-5" />
    </>
  ),
  arrowRight: <path d="M5 12h14M13 6l6 6-6 6" />,
  arrowLeft: <path d="M19 12H5m6-6-6 6 6 6" />,
  check: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="m8 12 3 3 5-6" />
    </>
  ),
  alert: <path d="M12 3 2 20h20L12 3zM12 10v4M12 17h.01" />,
  ban: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="m5.6 5.6 12.8 12.8" />
    </>
  ),
  info: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 11v5M12 8h.01" />
    </>
  ),
  book: <path d="M4 5a2 2 0 0 1 2-2h14v16H6a2 2 0 0 0-2 2V5zM4 19a2 2 0 0 0 2 2h14" />,
  grid: (
    <>
      <rect x="3" y="3" width="18" height="18" rx="2" />
      <path d="M3 9h18M3 15h18M9 3v18M15 3v18" />
    </>
  ),
  sigma: <path d="M18 5H6l6 7-6 7h12" />,
  shield: <path d="M12 3 4 6v6c0 4.5 3.2 7.8 8 9 4.8-1.2 8-4.5 8-9V6l-8-3z" />,
  pen: <path d="M4 20h4L19 9l-4-4L4 16v4zM13.5 6.5l4 4" />,
  external: (
    <path d="M14 4h6v6M20 4 10 14M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5" />
  ),
  plus: <path d="M12 5v14M5 12h14" />,
  x: <path d="M6 6l12 12M18 6 6 18" />,
  chart: <path d="M4 4v16h16M7 15l4-5 3 3 5-7" />,
  zap: <path d="M13 2 4 14h7l-1 8 9-12h-7l1-8z" />,
} satisfies Record<string, ReactNode>;

export type IconName = keyof typeof PATHS;

export function Icon({ name, size = 18, label }: { name: IconName; size?: number; label?: string }) {
  return (
    <svg
      className="icon"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      strokeLinecap="round"
      strokeLinejoin="round"
      role={label ? "img" : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
    >
      {PATHS[name]}
    </svg>
  );
}
