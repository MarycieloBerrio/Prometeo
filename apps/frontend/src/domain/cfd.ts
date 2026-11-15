/** CFD Physics Lab types (numerical simulations). Not experimental NASA measurements. */

export type CfdSimulation = {
  simulation_id: string;
  reference_trial_id: string;
  result_kind: string;
  solver: string;
  solver_version: string;
  model_type: string;
  inlet_velocity_m_s: number;
  inlet_velocity_cm_s: number;
  oxygen_context_percent: number | null;
  mesh_cell_count: number | null;
  residuals: Record<string, number>;
  mass_balance_error: number | null;
  mass_balance_status: string;
  mesh_independence: string;
  convergence_status: string;
  validation_status: string;
  has_field_sample: boolean;
  geometry_assumptions: string[];
  limitations: string[];
};

export type CfdFieldSample = {
  simulation_id: string;
  units: Record<string, string>;
  downsample_stride: number;
  n_points_source: number;
  points: Array<{ x: number; y: number; z: number; u_mag: number; p: number }>;
};

export type CfdInterpretation = {
  question: string;
  nasa_measured: string[];
  simulation_computed: string[];
  literature_mechanisms: string[];
  cannot_conclude: string[];
  sources: string[];
};

export const B16_CFD_TRIAL_IDS = [
  "BASS-II-B16-Vg072",
  "BASS-II-B16-Vg083",
  "BASS-II-B16-Vg167",
  "BASS-II-B16-Vg755",
] as const;
