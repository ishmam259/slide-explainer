import createClient from "openapi-fetch";

import type { components, paths } from "./schema";

/** Typed client for the local backend. Requests go to /api, which Next.js proxies. */
export const api = createClient<paths>({ baseUrl: "/api" });

export type Schemas = components["schemas"];
export type DeckSummary = Schemas["DeckSummary"];
export type DeckDetail = Schemas["DeckDetail"];
export type Slide = Schemas["Slide"];
export type Topic = Schemas["Topic"];
export type SourceList = Schemas["SourceList"];
export type DeckSource = Schemas["DeckSource"];
export type RunEstimate = Schemas["RunEstimate"];
export type Run = Schemas["Run"];
export type ExplanationDocument = Schemas["ExplanationDocument"];
export type EvidenceRef = Schemas["EvidenceRef"];
export type QaTurn = Schemas["QaTurn"];
export type QuizState = Schemas["QuizState"];
export type QuizFeedback = Schemas["QuizFeedback"];
export type Disagreement = Schemas["Disagreement"];
export type Health = Schemas["Health"];

export interface Problem {
  title: string;
  status: number;
  code: string;
  detail?: string | null;
}

export class ApiError extends Error {
  constructor(public problem: Problem) {
    super(problem.detail ?? problem.title);
  }
}

/** Unwrap an openapi-fetch result: return data or throw an ApiError with the problem body. */
export function unwrap<T>(res: { data?: T; error?: unknown; response: Response }): T {
  if (res.error !== undefined || res.data === undefined) {
    const err = res.error as Partial<Problem> | undefined;
    throw new ApiError({
      title: err?.title ?? res.response.statusText ?? "Request failed",
      status: err?.status ?? res.response.status,
      code: err?.code ?? "internal_error",
      detail: err?.detail ?? null,
    });
  }
  return res.data;
}
