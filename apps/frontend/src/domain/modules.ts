/** The five product modules of Prometeo (see AGENTS.md § Product modules). */
import type { IconName } from "@/components/ui/Icon";

export interface ProductModule {
  slug: string;
  number: string;
  name: string;
  /** Short nav label. */
  label: string;
  icon: IconName;
  /** One line: what the user does here. */
  purpose: string;
  /** Part of the guided Explore → Compare → Watch → Ask flow. */
  inFlow: boolean;
}

export const MODULES: ProductModule[] = [
  {
    slug: "explorer",
    number: "01",
    name: "Experiment Explorer",
    label: "Explorer",
    icon: "search",
    purpose: "Browse combustion trials by material, oxygen, airflow and source.",
    inFlow: true,
  },
  {
    slug: "compare",
    number: "02",
    name: "Comparison Lab",
    label: "Compare",
    icon: "compare",
    purpose: "Isolate a variable, inspect physical compatibility and read recorded differences.",
    inFlow: true,
  },
  {
    slug: "flamevision",
    number: "03",
    name: "FlameVision",
    label: "FlameVision",
    icon: "video",
    purpose: "Inspect source-linked flame video and the limits of visual tracking.",
    inFlow: true,
  },
  {
    slug: "assistant",
    number: "04",
    name: "Research Assistant",
    label: "Assistant",
    icon: "chat",
    purpose: "Ask an evidence-grounded question and inspect sources and limits.",
    inFlow: true,
  },
  {
    slug: "mission-safety",
    number: "05",
    name: "Mission Safety Explorer",
    label: "Future work",
    icon: "rocket",
    purpose: "See which evidence applies to a mission scenario, and the gaps.",
    inFlow: false,
  },
];

export function moduleBySlug(slug: string): ProductModule {
  const found = MODULES.find((m) => m.slug === slug);
  if (!found) throw new Error(`Unknown module: ${slug}`);
  return found;
}
