import { ApiError } from "./client";

/** Specific, actionable messages per problem code (FR-033). */
const FIXES: Record<string, string> = {
  api_key_missing: "Add OPENAI_API_KEY to backend/.env and restart the backend.",
  api_key_invalid: "OpenAI rejected the key. Check OPENAI_API_KEY in backend/.env.",
  libreoffice_missing: "Install LibreOffice, or set SLIDEX_SOFFICE in backend/.env to soffice.exe.",
  renderer_missing: "Run `uv run playwright install chromium` in the backend folder.",
  rate_limited: "OpenAI is rate-limiting requests. Wait a minute, then resume the run.",
  provider_unavailable: "OpenAI is unreachable. Check your connection, then resume the run.",
  search_unavailable: "Web search failed. Resume the run in a minute.",
  unsupported_file: "Upload a .pptx, .pdf, .png, .jpg or .webp file.",
  file_too_large: "Files must be under 200 MB.",
  too_many_slides: "Split the deck — the limit is 300 slides.",
  model_not_allowed: "A model above GPT-5.5 is configured. Check SLIDEX_MODEL_* in backend/.env.",
};

export function fixFor(code: string): string | undefined {
  return FIXES[code];
}

export function describeError(err: unknown): { title: string; detail: string } {
  if (err instanceof ApiError) {
    const fix = FIXES[err.problem.code];
    return {
      title: err.problem.detail ?? err.problem.title,
      detail: fix ?? (err.problem.detail ? err.problem.title : ""),
    };
  }
  if (err instanceof TypeError) {
    return { title: "Can't reach the backend.", detail: "Start it with: cd backend; uv run slidex serve" };
  }
  return { title: err instanceof Error ? err.message : "Something failed.", detail: "" };
}
