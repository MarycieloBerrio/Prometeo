/**
 * Port: everything the UI needs from the Evidence Engine.
 * UI code depends on this interface, never on `fetch` or URLs directly.
 */
import type {
  AskRequest,
  AskResponse,
  CompareRequest,
  CompareResponse,
  CoverageResponse,
  Trial,
} from "@prometeo/contracts";

import type { CfdFieldSample, CfdInterpretation, CfdSimulation } from "@/domain/cfd";

export interface TrialQuery {
  investigation?: string;
  material?: string;
  geometry?: string;
  phenomenon?: string;
  flow_direction?: string;
}

export interface EvidenceGateway {
  listTrials(query?: TrialQuery): Promise<Trial[]>;
  getTrial(id: string): Promise<Trial>;
  compare(request: CompareRequest): Promise<CompareResponse>;
  coverage(query?: Pick<TrialQuery, "material" | "geometry" | "flow_direction">): Promise<CoverageResponse>;
  ask(request: AskRequest): Promise<AskResponse>;
  listCfdSimulations(trialId?: string): Promise<CfdSimulation[]>;
  getCfdField(simulationId: string): Promise<CfdFieldSample>;
  getCfdInterpretation(simulationId: string): Promise<CfdInterpretation>;
}
