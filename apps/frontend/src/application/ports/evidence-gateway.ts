/**
 * Port: everything the UI needs from the Evidence Engine.
 * UI code depends on this interface, never on `fetch` or URLs directly.
 */
import type {
  AskRequest,
  AskResponse,
  AssistantModelsResponse,
  CompareRequest,
  CompareResponse,
  CoverageResponse,
  Trial,
} from "@prometeo/contracts";

export interface TrialQuery {
  investigation?: string;
  material?: string;
  geometry?: string;
  phenomenon?: string;
  flow_direction?: string;
}

/** An original source file, or the byte range of it that was asked for, streamed as stored. */
export interface SourceDocumentFile {
  body: ReadableStream<Uint8Array>;
  /** 200 for the whole file, 206 for a byte range. */
  status: number;
  contentType: string;
  contentLength: string | null;
  contentRange: string | null;
  acceptRanges: string | null;
}

export interface EvidenceGateway {
  listTrials(query?: TrialQuery): Promise<Trial[]>;
  getTrial(id: string): Promise<Trial>;
  compare(request: CompareRequest): Promise<CompareResponse>;
  coverage(query?: Pick<TrialQuery, "material" | "geometry" | "flow_direction">): Promise<CoverageResponse>;
  ask(request: AskRequest): Promise<AskResponse>;
  /** Models a question may pick; none when the engine runs without a language model. */
  assistantModels(): Promise<AssistantModelsResponse>;
  /** The file a retrieved excerpt was extracted from; null when there is no local copy. */
  sourceDocument(chunkId: string, range?: string | null): Promise<SourceDocumentFile | null>;
}
