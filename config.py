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

    # Config to load from .env file
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

# Instantiate settings to be imported across the application
settings = Settings()
