"use client";

import { useEffect, useRef, useState } from "react";

import { EdgeDiagram } from "@/components/EdgeDiagram";
import { chunkAnchor } from "@/lib/chunks";
import type { AnswerClaim, AskResponse } from "@/lib/types";

const STAGES = ["Route", "Graph", "Filings", "Answer", "Check"] as const;

function percent(confidence: number): string {
  return `${Math.round(confidence * 100)}%`;
}

function claimIds(claim: AnswerClaim): string[] {
  return claim.citation_chunk_ids ?? [];
}

export function TraceReveal({
  response,
  saved,
  notice,
}: {
  response: AskResponse;
  saved: boolean;
  notice: string | null;
}) {
  const [shown, setShown] = useState(0);
  const trace = response.trace;
  const rootRef = useRef<HTMLElement>(null);
  const anchorOwner = new Map<string, "passage" | "graph" | "allow">();
  for (const passage of trace.vector?.passages ?? []) {
    if (!anchorOwner.has(passage.chunk_id)) anchorOwner.set(passage.chunk_id, "passage");
  }
  for (const fact of trace.graph?.facts ?? []) {
    for (const id of fact.source_chunk_ids) {
      if (!anchorOwner.has(id)) anchorOwner.set(id, "graph");
    }
  }
  for (const id of trace.evidence.allowed_chunk_ids) {
    if (!anchorOwner.has(id)) anchorOwner.set(id, "allow");
  }
  const placed = new Set<string>();
  function placeAnchor(id: string, where: "passage" | "graph" | "allow"): boolean {
    if (anchorOwner.get(id) !== where || placed.has(id)) return false;
    placed.add(id);
    return true;
  }

  useEffect(() => {
    if (window.location.hash) {
      window.history.replaceState(
        null,
        "",
        window.location.pathname + window.location.search,
      );
    }
    rootRef.current?.scrollIntoView({ block: "start" });
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduce) {
      setShown(STAGES.length);
      return;
    }
    setShown(1);
    const timers = [1, 2, 3, 4].map((step) =>
      window.setTimeout(() => setShown(step + 1), step * 380),
    );
    return () => timers.forEach((timer) => window.clearTimeout(timer));
  }, [response]);

  const route = trace.route;
  const routeShift = route.model_route !== route.effective_route;

  return (
    <section ref={rootRef} className="mt-10 scroll-mt-6" aria-label="Answer trace">
      {saved && (
        <p className="mb-6 max-w-[68ch] text-stamp">
          {notice ?? "Saved run. This is a stored response, not a live call."}
        </p>
      )}
      <p className="max-w-[68ch] font-serif text-2xl leading-snug">{response.question}</p>
      <ol className="mt-6">
        {shown >= 1 && (
          <Stage n={1} title="Route">
            <p className="font-serif text-2xl leading-none">{route.effective_route}</p>
            <p className="mt-3 max-w-[68ch]">{route.rationale}</p>
            <p className="mt-3 text-sm text-slate">
              Confidence {percent(route.confidence)}
              {route.low_confidence_fallback
                ? ". Confidence was low, so the route fell back."
                : ""}
              {routeShift ? `. The router first said ${route.model_route}.` : ""}
            </p>
            {trace.graph != null && trace.vector != null && (
              <p className="mt-2 max-w-[68ch] text-sm text-slate">
                This ask retrieved both the graph and the filings. The route
                names which one the router chose.
              </p>
            )}
          </Stage>
        )}
        {shown >= 2 && (
          <Stage n={2} title="Graph">
            {trace.graph == null ? (
              <p>The graph was not queried.</p>
            ) : (
              <>
                <p className="mb-4 max-w-[68ch]">{trace.graph.plan_rationale}</p>
                <p className="mb-4 text-sm text-slate">
                  Templates {trace.graph.template_ids.join(", ")}
                </p>
                <EdgeDiagram
                  facts={trace.graph.facts}
                  passageIds={
                    new Set((trace.vector?.passages ?? []).map((passage) => passage.chunk_id))
                  }
                />
              </>
            )}
          </Stage>
        )}
        {shown >= 3 && (
          <Stage n={3} title="Filings">
            {trace.vector == null ? (
              <p>Filing search was not run.</p>
            ) : trace.vector.passages.length === 0 ? (
              <p>No filing passages came back.</p>
            ) : (
              <ul className="flex flex-col gap-5">
                {trace.vector.passages.map((passage) => (
                  <li
                    key={passage.chunk_id}
                    id={
                      placeAnchor(passage.chunk_id, "passage")
                        ? chunkAnchor(passage.chunk_id)
                        : undefined
                    }
                  >
                    <p className="text-sm text-slate">
                      {passage.section}, score {passage.score.toFixed(2)}
                    </p>
                    <p className="mt-1 max-w-[68ch]">{passage.text_preview}</p>
                    <p className="mt-1 font-mono text-[0.78rem] text-pine">
                      {passage.chunk_id}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </Stage>
        )}
        {shown >= 4 && (
          <Stage n={4} title="Answer">
            <p className="max-w-[68ch] font-serif text-2xl leading-relaxed">
              {trace.answer.summary}
            </p>
            <ul className="mt-5 flex flex-col gap-4">
              {trace.answer.claims.map((claim, index) => {
                const ids = claimIds(claim);
                return (
                  <li key={`${index}-${claim.text.slice(0, 24)}`}>
                    <p className="max-w-[68ch]">{claim.text}</p>
                    {ids.length > 0 ? (
                      <p className="mt-1">
                        {ids.map((id) => (
                          <a
                            key={id}
                            id={placeAnchor(id, "allow") ? chunkAnchor(id) : undefined}
                            href={`#${chunkAnchor(id)}`}
                            className="mr-3 font-mono text-[0.78rem] text-pine"
                          >
                            {id}
                          </a>
                        ))}
                      </p>
                    ) : (
                      <p className="mt-1 text-sm text-slate">No chunk cited.</p>
                    )}
                  </li>
                );
              })}
            </ul>
          </Stage>
        )}
        {shown >= 5 && (
          <Stage n={5} title="Check">
            <p className="max-w-[68ch]">
              {trace.validation.citations_valid
                ? "Every cited chunk was in this retrieval’s allowlist."
                : "A citation fell outside this retrieval’s allowlist."}
            </p>
            <p className="mt-2 max-w-[68ch]">
              {trace.answer.refused
                ? "The model refused. The evidence did not support an answer."
                : "The model answered from the evidence pack."}
            </p>
            <p className="mt-2 text-sm text-slate">
              {trace.validation.regenerated
                ? `The draft was regenerated. Attempts: ${trace.validation.attempts}.`
                : `Attempts: ${trace.validation.attempts}.`}{" "}
              Model {response.model}. Allowlist{" "}
              {trace.evidence.allowed_chunk_ids.length} chunks.
            </p>
            {trace.evidence.allowed_chunk_ids.length > 0 && (
              <details className="mt-3">
                <summary className="cursor-pointer text-sm text-pine">
                  Show allowlist
                </summary>
                <ul className="mt-2 flex flex-col gap-1">
                  {trace.evidence.allowed_chunk_ids.map((id) => (
                    <li key={id}>
                      <a
                        id={placeAnchor(id, "allow") ? chunkAnchor(id) : undefined}
                        href={`#${chunkAnchor(id)}`}
                        className="font-mono text-[0.78rem] text-slate"
                      >
                        {id}
                      </a>
                    </li>
                  ))}
                </ul>
              </details>
            )}
          </Stage>
        )}
      </ol>
    </section>
  );
}

function Stage({
  n,
  title,
  children,
}: {
  n: number;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <li className="grid grid-cols-[2rem_minmax(0,1fr)] gap-4 border-t border-rule py-6">
      <span className="font-serif text-lg text-pine">{n}</span>
      <div>
        <h2 className="mb-3 font-serif text-lg">{title}</h2>
        {children}
      </div>
    </li>
  );
}
