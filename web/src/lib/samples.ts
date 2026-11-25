export const TICKERS = [
  "AAPL",
  "AMZN",
  "GOOGL",
  "JNJ",
  "JPM",
  "META",
  "MSFT",
  "NFLX",
  "NVDA",
  "XOM",
] as const;

export type Sample = {
  id: string;
  label: string;
  question: string;
  ticker: (typeof TICKERS)[number];
};

export const SAMPLES: Sample[] = [
  {
    id: "nvda-products-risks",
    label: "NVIDIA products and risks",
    question:
      "What compute products does NVIDIA produce, and what geopolitical risks is it exposed to?",
    ticker: "NVDA",
  },
  {
    id: "aapl-products",
    label: "Apple products",
    question: "What product lines does Apple produce?",
    ticker: "AAPL",
  },
  {
    id: "aapl-applecare",
    label: "AppleCare",
    question: "What is AppleCare?",
    ticker: "AAPL",
  },
  {
    id: "aapl-bitcoin",
    label: "Bitcoin on Apple’s balance sheet",
    question: "How many Bitcoin does Apple hold on its balance sheet?",
    ticker: "AAPL",
  },
];
