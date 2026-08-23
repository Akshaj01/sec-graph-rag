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

    # Step E: entity resolution
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    ENTITY_SIMILARITY_THRESHOLD: float = 0.92

    # Config to load from .env file
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

# Instantiate settings to be imported across the application
settings = Settings()
