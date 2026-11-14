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
    label: "Explore",
    icon: "search",
    purpose: "Find trials by fuel, oxygen and airflow.",
    inFlow: true,
  },
  {
    slug: "compare",
    number: "02",
    name: "Comparison Lab",
    label: "Compare",
    icon: "compare",
    purpose: "Check if two trials can be compared, then see the difference.",
    inFlow: true,
  },
  {
    slug: "flamevision",
    number: "03",
    name: "FlameVision",
    label: "Watch",
    icon: "video",
    purpose: "Track the flame edge on NASA video and derive spread rate.",
    inFlow: true,
  },
  {
    slug: "assistant",
    number: "04",
    name: "Research Assistant",
    label: "Ask",
    icon: "chat",
    purpose: "Ask a question. Get an answer with its evidence and limits.",
    inFlow: true,
  },
  {
    slug: "mission-safety",
    number: "05",
    name: "Mission Safety Explorer",
    label: "Mission",
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
