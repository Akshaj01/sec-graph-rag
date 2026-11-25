import compare from "../../fixtures/compare-amzn-aws-prime.json";

// Recorded benchmark answers exported by export_compare_fixture.py.
type SystemRow = {
  route_effective: string;
  summary: string;
  cited_chunk_ids: string[];
  citations_valid: boolean;
  refused: boolean;
  score: number;
  judge_fact_hits: string[];
  judge_fact_misses: string[];
  judge_hallucination: boolean;
  judge_rationale: string;
};

type Compare = {
  item_id: string;
  suite: string;
  hop: number;
  ticker: string;
  question: string;
  required_facts: string[];
  runs: { file: string; hybrid: SystemRow; vector_only: SystemRow }[];
};

const DATA = compare as Compare;
const SHOWN = 0;

function score(value: number): string {
  return value.toFixed(2);
}

function Column({ title, row }: { title: string; row: SystemRow }) {
  return (
    <div className="border-t-2 border-ink pt-4">
      <div className="flex items-baseline justify-between gap-4">
        <h3 className="font-serif text-xl">{title}</h3>
        <p className="font-serif text-2xl leading-none">{score(row.score)}</p>
      </div>
      <p className="mt-1 text-sm text-slate">
        Route {row.route_effective} ·{" "}
        {row.citations_valid ? "citations valid" : "citations rejected"}
      </p>
      <p className="mt-4 leading-relaxed">{row.summary}</p>
      <ul className="mt-4 text-sm">
        {DATA.required_facts.map((fact) => {
          const hit = row.judge_fact_hits.includes(fact);
          return (
            <li key={fact} className={hit ? "text-ink" : "text-stamp"}>
              <span aria-hidden="true">{hit ? "✓ " : "✗ "}</span>
              <span className="sr-only">{hit ? "Hit: " : "Missed: "}</span>
              {fact}
            </li>
          );
        })}
      </ul>
      <details className="mt-4 text-sm text-slate">
        <summary className="cursor-pointer">Judge’s reasoning and citations</summary>
        <p className="mt-2 leading-relaxed">{row.judge_rationale}</p>
        <ul className="mt-2 font-mono text-xs break-all">
          {row.cited_chunk_ids.map((id) => (
            <li key={id}>{id}</li>
          ))}
        </ul>
      </details>
    </div>
  );
}

export function SideBySide() {
  const run = DATA.runs[SHOWN];
  const hybridScores = DATA.runs.map((r) => score(r.hybrid.score)).join(", ");
  const vectorScores = DATA.runs.map((r) => score(r.vector_only.score)).join(", ");

  return (
    <section id="side-by-side" className="mt-12 scroll-mt-6">
      <h2 className="font-serif text-2xl">One hop-2 question, both systems</h2>
      <p className="mt-3 max-w-[62ch] leading-relaxed">
        These are the recorded benchmark answers, not a live call. This is one
        of the hop-2 questions where vector-only lost points. The judge checks
        each answer against the required facts below.
      </p>

      <p className="mt-6 max-w-[68ch] font-serif text-xl leading-snug">
        {DATA.question}
        <span className="ml-2 font-sans text-sm text-slate">{DATA.ticker}</span>
      </p>

      <div className="mt-6 grid gap-8 sm:grid-cols-2">
        <Column title="Hybrid" row={run.hybrid} />
        <Column title="Vector-only" row={run.vector_only} />
      </div>

      <p className="mt-6 max-w-[62ch] text-sm text-slate">
        Run {SHOWN + 1} of {DATA.runs.length} shown. Judge scores across the
        three temperature-0 runs: hybrid {hybridScores}; vector-only{" "}
        {vectorScores}. Source: {run.file}, suite {DATA.suite}.
      </p>
    </section>
  );
}
