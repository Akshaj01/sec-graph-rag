import { SAVED_RUNS_ONLY } from "./mode";
import type { AskResponse } from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export function apiUrl(): string {
  return API_URL;
}

export async function askQuestion(body: {
  question: string;
  ticker: string;
}): Promise<AskResponse> {
  if (SAVED_RUNS_ONLY) {
    throw new Error("This build plays saved runs only.");
  }

  let response: Response;
  try {
    response = await fetch(`${API_URL}/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question: body.question,
        ticker: body.ticker || null,
      }),
    });
  } catch {
    throw new Error(`The local API is not reachable at ${API_URL}.`);
  }

  if (!response.ok) {
    let detail = `Ask failed (${response.status}).`;
    try {
      const payload: unknown = await response.json();
      if (
        payload &&
        typeof payload === "object" &&
        "detail" in payload &&
        typeof payload.detail === "string"
      ) {
        detail = payload.detail;
      }
    } catch {
      /* Keep the status line when the body is not JSON. */
    }
    throw new Error(detail);
  }

  return (await response.json()) as AskResponse;
}
