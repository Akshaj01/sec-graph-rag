import aaplBitcoin from "../../fixtures/aapl-bitcoin.json";
import aaplProducts from "../../fixtures/aapl-products.json";
import nvdaProductsRisks from "../../fixtures/nvda-products-risks.json";

import type { AskResponse } from "./types";

export type SavedRun = {
  saved_run: true;
  id: string;
  label: string;
  ticker: string;
  note: string;
  response: AskResponse;
};

function asSavedRun(value: unknown): SavedRun {
  return value as SavedRun;
}

export const SAVED_RUNS: SavedRun[] = [
  asSavedRun(nvdaProductsRisks),
  asSavedRun(aaplProducts),
  asSavedRun(aaplBitcoin),
];

export function findSavedRun(
  question: string,
  ticker: string,
): SavedRun | undefined {
  const q = question.trim().toLowerCase();
  const t = ticker.trim().toUpperCase();
  return SAVED_RUNS.find(
    (run) =>
      run.ticker.toUpperCase() === t &&
      run.response.question.trim().toLowerCase() === q,
  );
}
