/** The five product modules of Prometeo (see AGENTS.md § Product modules). */
export interface ProductModule {
  slug: string;
  number: string;
  name: string;
  summary: string;
  mvp: string;
}

export const MODULES: ProductModule[] = [
  {
    slug: "explorer",
    number: "01",
    name: "Experiment Explorer",
    summary:
      "Filter NASA microgravity combustion trials by fuel, oxygen, ventilation, geometry and phenomenon. Every trial shows its conditions, measurements, media and provenance.",
    mvp: "Curated, verifiable BASS-II sample",
  },
  {
    slug: "compare",
    number: "02",
    name: "Combustion Comparison Lab",
    summary:
      "Compare two or more trials. The Physics Validator flags incompatible conditions and withholds deltas when trials are not comparable.",
    mvp: "Pairwise comparison + O₂ × ventilation coverage map",
  },
  {
    slug: "flamevision",
    number: "03",
    name: "FlameVision",
    summary:
      "Overlay the tracked luminous flame front on real NASA video and derive spread velocity — always stating what feature is measured and whether it is validated.",
    mvp: "One processed and validated video",
  },
  {
    slug: "assistant",
    number: "04",
    name: "Research Assistant",
    summary:
      "Ask in natural language. Answers carry evidence tier, trials, computed facts, sources and limitations — and the engine refuses to extrapolate beyond the data.",
    mvp: "Cited answers with rule-based EvidenceRank",
  },
  {
    slug: "mission-safety",
    number: "05",
    name: "Mission Safety Explorer",
    summary:
      "Pick a mission scenario and see which experimental evidence applies and where the gaps are. Not a certification or risk predictor.",
    mvp: "Post-MVP",
  },
];
