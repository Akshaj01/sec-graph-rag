# SEC GraphRAG Project Rules

## Learning Protocol (STRICT REQUIREMENT)
- Do NOT build the entire project or Phase 1 all at once.
- Move strictly STEP-BY-STEP based on the roadmap.
- After each step, you must:
  1. Explain the "WHY" behind the technical decision or design pattern.
  2. Ask if the user understands or has questions before moving to the next step.
  3. Pause and wait for explicit confirmation to proceed.

## Technical Stack & Dependencies
- Language & Framework: Python 3.11+, FastAPI, Pydantic v2
- Graph Database: Neo4j (via official Neo4j Python Driver & Cypher)
- Vector Store / Embeddings: OpenAI text-embedding-3-small (and pgvector compatible)
- Data Source: SEC EDGAR API via `edgartools`
- Agent/LLM Provider: Gemini Pro / Claude API (via Instructor/Pydantic structured outputs)
- Infrastructure: Docker Compose (Neo4j with APOC plugins)

## Closed-World Ontology (STRICT REQUIREMENT)
To prevent unqueryable node explosion, enforce this strict schema in all extraction prompts and Pydantic models:
- **Allowed Entity Types (6)**: Company, Subsidiary, Supplier, ProductLine, RiskFactor, Executive
- **Allowed Relationship Types (8)**: OWNS_SUBSIDIARY, SUPPLIED_BY, COMPETES_WITH, EXPOSED_TO_RISK, PRODUCES_PRODUCT, DEPENDS_ON, LED_BY, OPERATES_IN_SEGMENT

## Phase 1 Build Roadmap
- Step A: Environment & Docker Setup (`docker-compose.yml`, `config.py`, `requirements.txt`) [COMPLETED]
- Step B: Pydantic Schemas & Ontology Definitions (`schemas.py`)
- Step C: SEC 10-K Fetching, Chunking & Hash Caching (`ingest.py` / SQLite)
- Step D: Schema Extraction with Gemini/Claude (`extractor.py`)
- Step E: Entity Resolution & Canonical Mapping (`resolver.py`)
- Step F: Idempotent Neo4j Cypher Writes (`graph_writer.py`)
