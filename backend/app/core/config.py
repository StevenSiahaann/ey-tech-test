"""
Application Configuration and Settings Module.
Loads environment variables with Pydantic Settings and defines Azure/Gemini portability parameters.
"""

import os
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # App Settings
    APP_NAME: str = "Conversational BI / Data Agent"
    APP_ENV: str = "development"
    APP_TIMEZONE: str = "Asia/Jakarta"
    AS_OF_DATE: Optional[str] = Field(default=None, description="Anchor date for seed data evaluation (YYYY-MM-DD). If None, defaults to current date.")

    # LLM Settings (Supports Gemini and Azure OpenAI seamlessly)
    LLM_PROVIDER: str = Field(default="gemini", description="Options: 'gemini' or 'azure_openai'")
    
    # Gemini Configuration
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-3.1-flash-lite"
    
    # Azure OpenAI Configuration
    AZURE_OPENAI_ENDPOINT: Optional[str] = None
    AZURE_OPENAI_API_KEY: Optional[str] = None
    AZURE_OPENAI_DEPLOYMENT: str = "gpt-4o"
    AZURE_OPENAI_API_VERSION: str = "2024-08-01-preview"

    # Embedding Configuration
    EMBEDDING_PROVIDER: str = "gemini" # 'gemini' or 'azure_openai'
    EMBEDDING_MODEL: str = "gemini-embedding-001"

    # Database Configuration (PostgreSQL & DuckDB Fallback)
    DATABASE_URL_RO: str = Field(
        default="postgresql://bi_readonly:password@localhost:5432/ey_bi",
        description="Read-only PostgreSQL connection string"
    )
    DATABASE_URL_ADMIN: Optional[str] = Field(
        default=None,
        description="Admin PostgreSQL connection string for migrations/seeding"
    )
    DUCKDB_PATH: str = "ey_bi.duckdb"

    # Cache & Session Memory (Redis)
    REDIS_URL: Optional[str] = "redis://localhost:6379/0"
    SESSION_TTL_SECONDS: int = 86400  # 24 Hours

    # Vector Database / Semantic Retrieval Store
    VECTOR_ENABLED: bool = False
    VECTOR_DB_URI: str = "http://localhost:19530"
    VECTOR_DB_TOKEN: Optional[str] = None
    MILVUS_URI: str = "http://localhost:19530"
    MILVUS_TOKEN: Optional[str] = None

    # Observability (Langfuse)
    LANGFUSE_ENABLED: bool = True
    LANGFUSE_PUBLIC_KEY: Optional[str] = None
    LANGFUSE_SECRET_KEY: Optional[str] = None
    LANGFUSE_HOST: str = "http://localhost:3005"

    # Safety and Limits
    MAX_ROWS: int = 1000
    SQL_TIMEOUT_MS: int = 10000
    MAX_SQL_RETRIES: int = 2

    model_config = SettingsConfigDict(
        env_file=(".env", "infra/.env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
