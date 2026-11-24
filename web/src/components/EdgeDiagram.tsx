import { chunkAnchor, relationshipPhrase } from "@/lib/chunks";
import type { TraceFact } from "@/lib/types";

const chunkClass = "mr-3 font-mono text-[0.78rem] text-pine";

export function EdgeDiagram({
  facts,
  passageIds,
}: {
  facts: TraceFact[];
  passageIds: ReadonlySet<string>;
}) {
  if (facts.length === 0) {
    return <p className="text-slate">No edges came back.</p>;
  }

  const owned = new Set<string>();

  return (
    <ul className="flex flex-col gap-4">
      {facts.map((fact, index) => (
        <li
          key={`${fact.source_name}-${fact.rel_type}-${fact.target_name}-${index}`}
          className="grid gap-1 border-b border-rule pb-3 sm:grid-cols-[minmax(0,1fr)_9rem_minmax(0,1fr)] sm:items-baseline sm:gap-4"
        >
          <span className="font-serif text-lg leading-snug">{fact.source_name}</span>
          <span className="font-serif text-sm italic text-slate">
            {relationshipPhrase(fact.rel_type)}
          </span>
          <span className="font-serif text-lg leading-snug">{fact.target_name}</span>
          {fact.source_chunk_ids.length > 0 && (
            <span className="sm:col-span-3">
              {fact.source_chunk_ids.map((id, chunkIndex) => {
                const placeHere = !passageIds.has(id) && !owned.has(id);
                if (placeHere) owned.add(id);
                return (
                  <a
                    key={`${id}-${chunkIndex}`}
                    id={placeHere ? chunkAnchor(id) : undefined}
                    href={`#${chunkAnchor(id)}`}
                    className={chunkClass}
                  >
                    {id}
                  </a>
                );
              })}
            </span>
          )}
        </li>
      ))}
    </ul>
  );
}
