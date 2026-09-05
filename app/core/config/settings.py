from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"


class PostgresSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="POSTGRES_")

    host: str = Field(default="localhost")
    port: int = Field(default=5432)
    db: str = Field(default="legal_analyzer")
    user: str = Field(default="legal_user")
    password: str = Field(default="change-me-postgres-password")
    pool_size: int = Field(default=20, ge=1, le=100)
    pool_overflow: int = Field(default=10, ge=0, le=50)
    echo: bool = Field(default=False)

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.db}"
        )

    @property
    def sync_database_url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.db}"
        )


class QdrantSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    QDRANT_HOST: str = Field(default="localhost")
    QDRANT_PORT: int = Field(default=6333)
    QDRANT_GRPC_PORT: int = Field(default=6334)
    QDRANT_API_KEY: str | None = Field(default=None)
    QDRANT_COLLECTION_PREFIX: str = Field(default="legal_")
    QDRANT_LOCAL_PATH: str | None = Field(default=None)

    @property
    def host(self) -> str:
        return self.QDRANT_HOST

    @property
    def port(self) -> int:
        return self.QDRANT_PORT

    @property
    def grpc_port(self) -> int:
        return self.QDRANT_GRPC_PORT

    @property
    def collection_prefix(self) -> str:
        return self.QDRANT_COLLECTION_PREFIX

    @property
    def local_path(self) -> str | None:
        return self.QDRANT_LOCAL_PATH

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}"


class RedisSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="REDIS_")

    host: str = Field(default="localhost")
    port: int = Field(default=6379)
    password: str | None = Field(default=None)
    db: int = Field(default=0)
    max_connections: int = Field(default=50, ge=1)

    @property
    def url(self) -> str:
        auth = f":{self.password}@" if self.password else ""
        return f"redis://{auth}{self.host}:{self.port}/{self.db}"


class OllamaSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="OLLAMA_",
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    host: str = Field(default="http://localhost:11434")
    default_model: str = Field(default="llama3.2")
    legal_model: str = Field(default="llama3.2")
    embedding_model: str = Field(default="nomic-embed-text")
    timeout_seconds: int = Field(default=300, ge=10)
    max_retries: int = Field(default=3, ge=1, le=10)

    @property
    def base_url(self) -> str:
        return self.host.rstrip("/")


class MinioSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MINIO_")

    host: str = Field(default="localhost")
    port: int = Field(default=9000)
    console_port: int = Field(default=9001)
    access_key: str = Field(default="minioadmin")
    secret_key: str = Field(default="minioadmin123")
    bucket_documents: str = Field(default="legal-documents")
    bucket_reports: str = Field(default="legal-reports")
    secure: bool = Field(default=False)

    @property
    def endpoint(self) -> str:
        return f"{self.host}:{self.port}"


class JwtSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="JWT_")

    algorithm: str = Field(default="HS256")
    access_token_expire_minutes: int = Field(default=30, ge=1)
    refresh_token_expire_days: int = Field(default=7, ge=1)


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="APP_")

    name: str = Field(default="Post-Meeting Legal Analyzer")
    env: str = Field(default="development")
    debug: bool = Field(default=False)
    secret_key: str = Field(default="change-me-to-a-256-bit-random-value")
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)
    workers: int = Field(default=2, ge=1)


class SecuritySettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SECURITY_", extra="ignore")

    bcrypt_rounds: int = Field(default=12, ge=4, le=31)


class FileUploadSettings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    max_upload_size_mb: int = Field(default=100, ge=1)
    allowed_mime_types: list[str] = Field(
        default=[
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "text/plain",
            "text/markdown",
            "text/x-markdown",
        ]
    )

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024


class AiSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AI_", extra="ignore")

    chunk_size_tokens: int = Field(default=512, ge=64, le=4096)
    chunk_overlap_tokens: int = Field(default=64, ge=0, le=512)
    max_retrieval_chunks: int = Field(default=20, ge=1, le=100)
    rerank_top_k: int = Field(default=8, ge=1, le=50)
    max_context_tokens: int = Field(default=8192, ge=512, le=32768)
    embedding_dimension: int = Field(default=768, ge=128)
    vector_similarity_threshold: float = Field(default=0.35, ge=0.0, le=1.0)


class LoggingSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LOG_")

    level: str = Field(default="INFO")
    format: str = Field(default="json")
    request_body: bool = Field(default=False)


class MetricsSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="METRICS_", extra="ignore")

    enabled: bool = Field(default=True)
    port: int = Field(default=9090)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app: AppSettings = Field(default_factory=AppSettings)
    postgres: PostgresSettings = Field(default_factory=PostgresSettings)
    qdrant: QdrantSettings = Field(default_factory=QdrantSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    ollama: OllamaSettings = Field(default_factory=OllamaSettings)
    minio: MinioSettings = Field(default_factory=MinioSettings)
    jwt: JwtSettings = Field(default_factory=JwtSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    upload: FileUploadSettings = Field(default_factory=FileUploadSettings)
    ai: AiSettings = Field(default_factory=AiSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    metrics: MetricsSettings = Field(default_factory=MetricsSettings)


def get_settings() -> Settings:
    return Settings()
