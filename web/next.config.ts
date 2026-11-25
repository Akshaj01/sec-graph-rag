import type { NextConfig } from "next";

// Saved-runs-only build: the page plays the stored responses in fixtures/
// and never calls the API, so a public deploy costs no model calls.
// On by default on Vercel (VERCEL=1). Set SAVED_RUNS_ONLY=1 or 0 to choose.
const savedRunsOnly =
  process.env.SAVED_RUNS_ONLY !== undefined
    ? process.env.SAVED_RUNS_ONLY === "1"
    : process.env.VERCEL === "1";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  devIndicators: false,
  env: {
    SAVED_RUNS_ONLY: savedRunsOnly ? "1" : "0",
  },
};

export default nextConfig;
