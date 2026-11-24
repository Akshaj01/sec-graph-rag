import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "How it works",
  description: "How a 10-K question becomes a cited answer.",
};

const STEPS = [
  {
    title: "Read the filing",
    body: "Items 1, 1A, and 7 are split into chunks and cached by content hash.",
  },
  {
    title: "Extract a closed ontology",
    body: "A model writes JSON for six entity types and eight relationship types. A node or edge outside that list is not stored.",
  },
  {
    title: "Write two indexes of the same chunks",
    body: "Resolved entities merge into Neo4j. Each edge keeps the chunk ids it came from. The same chunks are embedded into pgvector.",
  },
  {
    title: "Route the question",
    body: "A smaller model chooses graph, vector, or both. Graph queries run from allowlisted Cypher templates. The model does not write the query.",
  },
  {
    title: "Answer inside an allowlist",
    body: "The draft may cite only chunk ids from this retrieval. A citation outside that set is rejected, and the draft can be regenerated once.",
  },
];

const ENTITIES = [
  "Company",
  "Subsidiary",
  "Supplier",
  "ProductLine",
  "RiskFactor",
  "Executive",
];

const RELATIONSHIPS = [
  "OWNS_SUBSIDIARY",
  "SUPPLIED_BY",
  "COMPETES_WITH",
  "EXPOSED_TO_RISK",
  "PRODUCES_PRODUCT",
  "DEPENDS_ON",
  "LED_BY",
  "OPERATES_IN_SEGMENT",
];

export default function HowItWorksPage() {
  return (
    <article className="max-w-3xl">
      <h1 className="font-serif text-4xl leading-tight">How it works</h1>
      <p className="mt-4 max-w-[62ch] text-lg leading-relaxed">
        One question walks through a fixed pipeline. The Ask page shows the
        route, the edges, the passages, and the citation check for that walk.
      </p>

      <ol className="mt-8">
        {STEPS.map((step, index) => (
          <li
            key={step.title}
            className="grid grid-cols-[2rem_minmax(0,1fr)] gap-4 border-t border-rule py-5"
          >
            <span className="font-serif text-lg text-pine">{index + 1}</span>
            <div>
              <h2 className="font-serif text-xl">{step.title}</h2>
              <p className="mt-2 max-w-[62ch]">{step.body}</p>
            </div>
          </li>
        ))}
      </ol>

      <h2 className="mt-10 font-serif text-2xl">Ontology</h2>
      <p className="mt-3 max-w-[62ch]">
        Companies, subsidiaries, and suppliers are shared nodes. Products,
        risks, and executives are scoped to the issuer, so two filings cannot
        collapse onto the same node just because the names match.
      </p>
      <div className="mt-6 grid gap-8 sm:grid-cols-2">
        <div>
          <h3 className="font-serif text-lg">Entities</h3>
          <ul className="mt-2">
            {ENTITIES.map((name) => (
              <li key={name} className="border-t border-rule py-2">
                {name}
              </li>
            ))}
          </ul>
        </div>
        <div>
          <h3 className="font-serif text-lg">Relationships</h3>
          <ul className="mt-2">
            {RELATIONSHIPS.map((name) => (
              <li key={name} className="border-t border-rule py-2 text-sm">
                {name}
              </li>
            ))}
          </ul>
        </div>
      </div>

      <p className="mt-10 max-w-[62ch] text-sm text-slate">
        On a normal ask, both indexes are queried even when the router chose
        one of them. The route on the Ask page is that choice. The vector-only
        switch on the API skips the graph, which is how the ablation is run.
      </p>
    </article>
  );
}
