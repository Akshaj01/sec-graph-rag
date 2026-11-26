import aaplCompetesMeta from "../../fixtures/compare-aapl-competes-meta.json";
import msftProducts from "../../fixtures/compare-msft-products.json";

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
  judge_hallucination: boolean | null; // null when the answer refused (no judge call)
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

type Example = {
  data: Compare;
  heading: string;
  caption: string;
};

const EXAMPLES: Example[] = [
  {
    data: aaplCompetesMeta as Compare,
    heading: "Where the graph helps",
    caption:
      "The question asks what the knowledge graph says, so vector-only, which has no graph, refused. The hybrid answer comes from an Apple → Meta COMPETES_WITH edge extracted from Meta's 10-K.",
  },
  {
    data: msftProducts as Compare,
    heading: "Where it hurts",
    caption:
      "The router sent this to the graph, which listed the product lines it held and missed Azure and Xbox. Vector search found the segment overview that names both.",
  },
];

const SHOWN = 0;

function score(value: number): string {
  return value.toFixed(2);
}

function Column({ title, row, facts }: { title: string; row: SystemRow; facts: string[] }) {
  return (
    <div className="border-t-2 border-ink pt-4">
      <div className="flex items-baseline justify-between gap-4">
        <h4 className="font-serif text-xl">{title}</h4>
        <p className="font-serif text-2xl leading-none">{score(row.score)}</p>
      </div>
      <p className="mt-1 text-sm text-slate">
        Route {row.route_effective} ·{" "}
        {row.refused ? "refused" : row.citations_valid ? "citations valid" : "citations rejected"}
      </p>
      <p className="mt-4 leading-relaxed">{row.summary}</p>
      <ul className="mt-4 text-sm">
        {facts.map((fact) => {
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

function ExampleBlock({ example }: { example: Example }) {
  const { data } = example;
  const run = data.runs[SHOWN];
  const hybridScores = data.runs.map((r) => score(r.hybrid.score)).join(", ");
  const vectorScores = data.runs.map((r) => score(r.vector_only.score)).join(", ");

  return (
    <div className="mt-10">
      <h3 className="font-serif text-xl text-pine">{example.heading}</h3>
      <p className="mt-2 max-w-[68ch] font-serif text-xl leading-snug">
        {data.question}
        <span className="ml-2 font-sans text-sm text-slate">
          {data.ticker} · hop {data.hop}
        </span>
      </p>
      <p className="mt-2 max-w-[62ch] text-sm leading-relaxed">{example.caption}</p>

      <div className="mt-6 grid gap-8 sm:grid-cols-2">
        <Column title="Hybrid" row={run.hybrid} facts={data.required_facts} />
        <Column title="Vector-only" row={run.vector_only} facts={data.required_facts} />
      </div>

      <p className="mt-4 max-w-[62ch] text-sm text-slate">
        Run {SHOWN + 1} of {data.runs.length} shown. Scores across the three
        runs: hybrid {hybridScores}; vector-only {vectorScores}. Source:{" "}
        {run.file}.
      </p>
    </div>
  );
}

export function SideBySide() {
  return (
    <section id="side-by-side" className="mt-12 scroll-mt-6">
      <h2 className="font-serif text-2xl">Both systems, side by side</h2>
      <p className="mt-3 max-w-[62ch] leading-relaxed">
        Recorded benchmark answers, not a live call. Overall the two systems
        tie, but not question by question: on a few questions one wins in every
        run. Here is one each way. The judge checks each answer against the
        required facts listed under it.
      </p>
      {EXAMPLES.map((example) => (
        <ExampleBlock key={example.data.item_id} example={example} />
      ))}
    </section>
  );
}
