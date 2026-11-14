/** Display helpers. Formatting only: no physics and no derived values are computed here. */
import type { Quantity } from "@prometeo/contracts";

import type { IconName } from "@/components/ui/Icon";

export function formatQuantity(q: Quantity | null | undefined): string | null {
  if (!q) return null;
  // Trim float noise without adding trailing zeros that would suggest extra precision.
  const value = Number(q.value.toPrecision(6)).toString();
  return q.unit === "%" ? `${value}%` : `${value} ${q.unit}`;
}

/** snake_case → "Sentence case". */
export function humanize(value: string): string {
  const text = value.replace(/_/g, " ");
  return text.charAt(0).toUpperCase() + text.slice(1);
}

export const GEOMETRIES = ["sheet", "cylinder", "sphere", "droplet", "other"] as const;
export const FLOW_DIRECTIONS = ["concurrent", "opposed", "quiescent"] as const;
export const PHENOMENA = ["ignition", "spread", "extinction"] as const;

export const PHENOMENON_ICON: Record<string, IconName> = {
  ignition: "zap",
  spread: "arrowRight",
  extinction: "x",
};

/** Variables the Physics Validator knows about, in display order. */
export const VARIABLES: { key: string; label: string; icon: IconName }[] = [
  { key: "fuel", label: "Fuel", icon: "flame" },
  { key: "geometry", label: "Geometry", icon: "box" },
  { key: "thickness", label: "Thickness", icon: "layers" },
  { key: "thermal_regime", label: "Thermal regime", icon: "layers" },
  { key: "oxygen", label: "Oxygen", icon: "oxygen" },
  { key: "flow_speed", label: "Flow speed", icon: "wind" },
  { key: "flow_direction", label: "Flow direction", icon: "wind" },
  { key: "pressure", label: "Pressure", icon: "gauge" },
];

/** First value of a search param that may be repeated. */
export function firstParam(value: string | string[] | undefined): string | undefined {
  const v = Array.isArray(value) ? value[0] : value;
  return v ? v : undefined;
}

export function allParams(value: string | string[] | undefined): string[] {
  if (!value) return [];
  return (Array.isArray(value) ? value : [value]).filter(Boolean);
}
