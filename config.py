from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    # Neo4j Database Settings
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USERNAME: str = "neo4j"
    NEO4J_PASSWORD: str = "password"

    # LLM Provider Keys
    OPENAI_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    
    # SEC EDGAR API Requirements
    # The SEC requires a user agent string in the format: Company Name admin@company.com
    USER_AGENT_EMAIL: str = "your.name@example.com"

    # Step C: ingest / chunk cache
    INGEST_CACHE_PATH: str = "./data/ingest_cache.db"
    # ~4 chars/token is a practical English approximation (avoids a tokenizer dependency in Step C)
    CHUNK_SIZE_TOKENS: int = 3000
    CHUNK_OVERLAP_TOKENS: int = 200
    CHARS_PER_TOKEN: int = 4

    # Step D: Claude structured extraction
    CLAUDE_MODEL: str = "claude-sonnet-4-5"
    EXTRACTION_MAX_RETRIES: int = 3
    EXTRACTION_MAX_TOKENS: int = 4096
    EXTRACTION_CACHE_PATH: str = "./data/extraction_cache.db"

    # Cost guardrails (USD). Run `python budget.py TICKER` before full corpus.
    MAX_EXTRACTION_BUDGET_USD: Optional[float] = 5.0
    EXTRACTION_INPUT_COST_PER_MTOK: float = 3.0
    EXTRACTION_OUTPUT_COST_PER_MTOK: float = 15.0
    EMBEDDING_COST_PER_MTOK: float = 0.02

    # Step E: entity resolution
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    ENTITY_SIMILARITY_THRESHOLD: float = 0.92
    EMBEDDING_DIMENSIONS: int = 1536  # text-embedding-3-small output size

    # Step G: Postgres + pgvector
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "secgraph"
    POSTGRES_PASSWORD: str = "password"
    POSTGRES_DB: str = "secgraph"

    @property
    def postgres_dsn(self) -> str:
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # Step K: question router (graph vs vector)
    ROUTER_MODEL: str = "claude-haiku-4-5"
    ROUTER_CONFIDENCE_THRESHOLD: float = 0.75
    ROUTER_MAX_RETRIES: int = 2
    ROUTER_MAX_TOKENS: int = 256
    ROUTER_LOG_PATH: str = "./data/route_log.db"

    # Step L: graph retrieval (parameterized templates)
    GRAPH_RETRIEVAL_LIMIT: int = 25

    # Step M: vector retrieval
    VECTOR_RETRIEVAL_K: int = 5

    # Step N/O: grounded answer + citation validation
    ANSWER_MODEL: str = "claude-sonnet-4-5"
    ANSWER_MAX_RETRIES: int = 2
    ANSWER_MAX_TOKENS: int = 2048
    # Extra full regenerate attempts after citation validation fails (0 = validate only).
    ANSWER_CITATION_REGENERATE_ATTEMPTS: int = 1

    # Step R: Haiku-ish pricing for router/graph-plan cost estimates
    HAIKU_INPUT_COST_PER_MTOK: float = 0.80
    HAIKU_OUTPUT_COST_PER_MTOK: float = 4.0
    # Keyword recall threshold for binary "pass" notes (soft accuracy still uses raw recall)
    BENCHMARK_KEYWORD_PASS_THRESHOLD: float = 0.5

    # Step T: FastAPI
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000

    # Config to load from .env file
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

# Instantiate settings to be imported across the application
settings = Settings()
