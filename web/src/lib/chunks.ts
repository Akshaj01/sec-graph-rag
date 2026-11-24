export function chunkAnchor(chunkId: string): string {
  return `chunk-${chunkId.replace(/[^a-zA-Z0-9_-]/g, "-")}`;
}

const REL_PHRASE: Record<string, string> = {
  OWNS_SUBSIDIARY: "owns subsidiary",
  SUPPLIED_BY: "is supplied by",
  COMPETES_WITH: "competes with",
  EXPOSED_TO_RISK: "is exposed to risk",
  PRODUCES_PRODUCT: "produces",
  DEPENDS_ON: "depends on",
  LED_BY: "is led by",
  OPERATES_IN_SEGMENT: "operates in segment",
};

export function relationshipPhrase(relType: string): string {
  return REL_PHRASE[relType] ?? relType.replaceAll("_", " ").toLowerCase();
}
