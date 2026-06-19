// Shared fetch helper with a configurable timeout. The live comparison can run long — a
// cold bootstrap credible interval on a fresh reference takes a while — so the default is
// generous (10 min) and tunable via NEXT_PUBLIC_API_TIMEOUT_MS. Set it to 0 to disable the
// client timeout entirely and rely on the server/platform. Quick calls (health, detect)
// pass SHORT_TIMEOUT_MS so a hung connection fails fast instead of blocking the UI.

export const API_TIMEOUT_MS = Number(process.env.NEXT_PUBLIC_API_TIMEOUT_MS ?? 600_000);
export const SHORT_TIMEOUT_MS = 20_000;

export async function fetchWithTimeout(
  input: RequestInfo | URL,
  init: RequestInit = {},
  timeoutMs: number = API_TIMEOUT_MS,
): Promise<Response> {
  if (!timeoutMs || timeoutMs <= 0) return fetch(input, init);
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(input, { ...init, signal: controller.signal });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new Error(`request timed out after ${Math.round(timeoutMs / 1000)}s`);
    }
    throw err;
  } finally {
    clearTimeout(id);
  }
}
