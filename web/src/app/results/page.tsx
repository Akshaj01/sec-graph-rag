import type { Metadata } from "next";

import { SideBySide } from "@/components/SideBySide";

export const metadata: Metadata = {
  title: "Results",
  description:
    "Hybrid versus vector-only scores on 44 hop-stratified 10-K questions.",
};

type AnswerRow = {
  hop: string;
  hybrid: string;
  vector: string;
  n: string;
  lead: "hybrid" | "vector" | "tie";
};

const ANSWER_ROWS: readonly AnswerRow[] = [
  { hop: "Hop 0, definitions", hybrid: "1.00", vector: "1.00", n: "8", lead: "tie" },
  { hop: "Hop 1, single edge", hybrid: "0.91", vector: "0.87", n: "16", lead: "hybrid" },
  { hop: "Hop 2, compare / multi-rel", hybrid: "0.94", vector: "0.96", n: "8", lead: "vector" },
  { hop: "Out of scope, must refuse", hybrid: "1.00", vector: "1.00", n: "12", lead: "tie" },
  { hop: "Overall mean", hybrid: "0.96", vector: "0.94", n: "44", lead: "hybrid" },
];

const RETRIEVAL_ROWS = [
  { name: "Graph", recall5: "0.43", recall10: "0.51", mrr: "0.38" },
  { name: "Vector", recall5: "0.84", recall10: "0.94", mrr: "0.70" },
  { name: "Hybrid", recall5: "0.85", recall10: "0.93", mrr: "0.68" },
];

export default function ResultsPage() {
  return (
    <article className="max-w-3xl">
      <h1 className="font-serif text-4xl leading-tight">Results</h1>
      <p className="mt-4 max-w-[62ch] text-lg leading-relaxed">
        Hybrid mean is 0.96. Vector-only mean is 0.94. The two tie: in a
        paired bootstrap the 95% interval on the gap includes zero overall and
        on every hop. An earlier hop-2 lead came from two bugs, a judge that
        marked real products as invented and a second year of Apple filings in
        the index. The score is an LLM judge against required facts. Out of
        scope means a correct refusal. Each cell is the mean of three
        temperature-0 runs.
      </p>

      <table className="mt-8 w-full border-collapse text-left text-sm">
        <caption className="mb-3 text-left font-serif text-xl">
          Answer score by hop
        </caption>
        <thead>
          <tr className="border-b border-ink">
            <th scope="col" className="py-2 pr-4 font-normal">Hop</th>
            <th scope="col" className="py-2 pr-4 font-normal">Hybrid</th>
            <th scope="col" className="py-2 pr-4 font-normal">Vector-only</th>
            <th scope="col" className="py-2 font-normal">n</th>
          </tr>
        </thead>
        <tbody>
          {ANSWER_ROWS.map((row) => (
            <tr key={row.hop} className="border-b border-rule">
              <th scope="row" className="py-3 pr-4 font-normal">{row.hop}</th>
              <td className={`py-3 pr-4 ${row.lead === "vector" ? "" : "font-semibold"}`}>
                {row.hybrid}
              </td>
              <td className={`py-3 pr-4 ${row.lead === "hybrid" ? "" : "font-semibold"}`}>
                {row.vector}
              </td>
              <td className="py-3">{row.n}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <SideBySide />

      <p className="mt-10 max-w-[62ch] leading-relaxed">
        Retrieval is scored separately, on 32 answerable items. Hybrid and
        vector are within 0.02 of each other on every metric: recall@5 0.85
        and 0.84, recall@10 0.93 and 0.94, MRR 0.68 and 0.70.
      </p>

      <table className="mt-6 w-full border-collapse text-left text-sm">
        <caption className="mb-3 text-left font-serif text-xl">
          Retrieval
        </caption>
        <thead>
          <tr className="border-b border-ink">
            <th scope="col" className="py-2 pr-4 font-normal">Index</th>
            <th scope="col" className="py-2 pr-4 font-normal">Recall@5</th>
            <th scope="col" className="py-2 pr-4 font-normal">Recall@10</th>
            <th scope="col" className="py-2 font-normal">MRR</th>
          </tr>
        </thead>
        <tbody>
          {RETRIEVAL_ROWS.map((row) => (
            <tr key={row.name} className="border-b border-rule">
              <th scope="row" className="py-3 pr-4 font-normal">{row.name}</th>
              <td className="py-3 pr-4">{row.recall5}</td>
              <td className="py-3 pr-4">{row.recall10}</td>
              <td className="py-3">{row.mrr}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <p className="mt-8 max-w-[62ch] text-sm text-slate">
        Suite multi_company_smoke v4, one pinned 10-K per company. The planner,
        router, answer, and judge ran at temperature 0. The judge reads the
        passages each answer cites. Its agreement with hand labels on a
        held-out sheet is linear weighted κ 0.79.
      </p>
    </article>
  );
}
