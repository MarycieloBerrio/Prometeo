/** Frontend composition root: picks the EvidenceGateway implementation. Server-side only. */
import "server-only";

import type { EvidenceGateway } from "@/application/ports/evidence-gateway";
import { HttpEvidenceGateway } from "@/infrastructure/http/http-evidence-gateway";

const apiUrl = process.env.PROMETEO_API_URL ?? "http://localhost:8000";

export const gateway: EvidenceGateway = new HttpEvidenceGateway(apiUrl);
