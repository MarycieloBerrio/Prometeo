/**
 * Public API contract between apps/backend (FastAPI) and apps/frontend (Next.js).
 *
 * `generated.ts` is produced from `openapi.json` by `pnpm contracts` (repo root).
 * Re-run it whenever backend DTOs in `adapters/inbound/http/schemas.py` change.
 */
import type { components } from "./generated";

type Schemas = components["schemas"];

export type Trial = Schemas["TrialOut"];
export type Quantity = Schemas["QuantityOut"];
export type Provenance = Schemas["ProvenanceOut"];
export type Measurement = Schemas["MeasurementOut"];
export type CompareRequest = Schemas["CompareRequest"];
export type CompareResponse = Schemas["CompareResponse"];
export type CoverageResponse = Schemas["CoverageResponse"];
export type AskRequest = Schemas["AskRequest"];
export type AskResponse = Schemas["AskResponse"];
