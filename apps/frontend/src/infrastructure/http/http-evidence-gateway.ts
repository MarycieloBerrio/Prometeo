/** Adapter: EvidenceGateway over the FastAPI backend (apps/backend). */
import type {
  AskRequest,
  AskResponse,
  CompareRequest,
  CompareResponse,
  CoverageResponse,
  Trial,
} from "@prometeo/contracts";

import type { EvidenceGateway, TrialQuery } from "@/application/ports/evidence-gateway";
import type { CfdFieldSample, CfdInterpretation, CfdSimulation } from "@/domain/cfd";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

export class HttpEvidenceGateway implements EvidenceGateway {
  constructor(private readonly baseUrl: string) {}

  listTrials(query: TrialQuery = {}): Promise<Trial[]> {
    return this.get(`/api/v1/trials${toSearch(query)}`);
  }

  getTrial(id: string): Promise<Trial> {
    return this.get(`/api/v1/trials/${encodeURIComponent(id)}`);
  }

  compare(request: CompareRequest): Promise<CompareResponse> {
    return this.post("/api/v1/comparisons", request);
  }

  coverage(query: TrialQuery = {}): Promise<CoverageResponse> {
    return this.get(`/api/v1/coverage${toSearch(query)}`);
  }

  ask(request: AskRequest): Promise<AskResponse> {
    return this.post("/api/v1/assistant/ask", request);
  }

  listCfdSimulations(trialId?: string): Promise<CfdSimulation[]> {
    const q = trialId ? `?trial_id=${encodeURIComponent(trialId)}` : "";
    return this.get(`/api/v1/cfd/simulations${q}`);
  }

  getCfdField(simulationId: string): Promise<CfdFieldSample> {
    return this.get(`/api/v1/cfd/simulations/${encodeURIComponent(simulationId)}/field`);
  }

  getCfdInterpretation(simulationId: string): Promise<CfdInterpretation> {
    return this.get(`/api/v1/cfd/simulations/${encodeURIComponent(simulationId)}/interpretation`);
  }

  private async get<T>(path: string): Promise<T> {
    return this.handle<T>(await fetch(`${this.baseUrl}${path}`));
  }

  private async post<T>(path: string, body: unknown): Promise<T> {
    const res = await fetch(`${this.baseUrl}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    return this.handle<T>(res);
  }

  private async handle<T>(res: Response): Promise<T> {
    if (!res.ok) {
      const detail = await res.text();
      throw new ApiError(res.status, detail || res.statusText);
    }
    return (await res.json()) as T;
  }
}

function toSearch(query: object): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (typeof value === "string" && value) params.set(key, value);
  }
  const s = params.toString();
  return s ? `?${s}` : "";
}
