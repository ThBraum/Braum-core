from functools import lru_cache
from urllib.parse import quote_plus

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = Field(
        default="Braum Core API", validation_alias=AliasChoices("APP_NAME", "app_name")
    )
    environment: str = Field(
        default="development", validation_alias=AliasChoices("APP_ENV", "environment")
    )
    version: str = Field(
        default="0.1.0", validation_alias=AliasChoices("APP_VERSION", "app_version")
    )
    dev: bool = Field(default=False, validation_alias=AliasChoices("DEV_MODE", "DEV", "dev_mode"))

    secret_key: str = Field(
        default="change-me", validation_alias=AliasChoices("SECRET_KEY", "secret_key")
    )
    jwt_secret: str = Field(
        default="change-me",
        validation_alias=AliasChoices("JWT_SECRET", "SECRET_KEY", "jwt_secret"),
    )
    jwt_algorithm: str = Field(
        default="HS256", validation_alias=AliasChoices("JWT_ALGORITHM", "jwt_algorithm")
    )

    postgres_user: str = Field(
        default="postgres", validation_alias=AliasChoices("POSTGRES_USER", "postgres_user")
    )
    postgres_password: str = Field(
        default="postgres", validation_alias=AliasChoices("POSTGRES_PASSWORD", "postgres_password")
    )
    postgres_db: str = Field(
        default="braum", validation_alias=AliasChoices("POSTGRES_DB", "postgres_db")
    )
    postgres_host: str = Field(
        default="localhost", validation_alias=AliasChoices("POSTGRES_HOST", "postgres_host")
    )
    postgres_port: int = Field(
        default=5432, validation_alias=AliasChoices("POSTGRES_PORT", "postgres_port")
    )

    database_url: str = Field(
        default="postgresql+psycopg://postgres:postgres@localhost:5432/braum",
        validation_alias=AliasChoices("DATABASE_URL", "database_url"),
    )

    cors_localhost: bool = Field(
        default=False, validation_alias=AliasChoices("APP_DEBUG", "cors_localhost")
    )
    free_general_questions: int = Field(
        default=10,
        validation_alias=AliasChoices("GUEST_SESSION_MAX_QUESTIONS", "FREE_GENERAL_QUESTIONS"),
    )
    allowed_sql_tables: str = Field(
        default="users,orders,products",
        validation_alias=AliasChoices("SQL_ALLOWED_TABLES", "ALLOWED_SQL_TABLES"),
    )
    realtime_search_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices("REALTIME_SEARCH_ENABLED", "realtime_search_enabled"),
    )
    realtime_search_timeout_seconds: float = Field(
        default=1.8,
        validation_alias=AliasChoices(
            "REALTIME_SEARCH_TIMEOUT_SECONDS", "realtime_search_timeout_seconds"
        ),
    )
    realtime_search_cache_ttl_seconds: int = Field(
        default=300,
        validation_alias=AliasChoices(
            "REALTIME_SEARCH_CACHE_TTL_SECONDS", "realtime_search_cache_ttl_seconds"
        ),
    )
    realtime_search_max_sources: int = Field(
        default=3,
        validation_alias=AliasChoices(
            "REALTIME_SEARCH_MAX_SOURCES", "realtime_search_max_sources"
        ),
    )

    debug: bool = Field(default=False, validation_alias=AliasChoices("DEBUG", "debug"))
    log_file_path: str = Field(
        default="",
        validation_alias=AliasChoices("LOG_FILE_PATH", "log_file_path"),
    )

    php_sinfonia_url: str = ""
    prequest_socks_host: str = "socks"
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    ds_login_teste: str = ""
    cd_senha_teste: str = ""

    @property
    def normalized_allowed_sql_tables(self) -> list[str]:
        raw_values = self.allowed_sql_tables.split(",")
        values = [value.strip() for value in raw_values if value and value.strip()]
        if values:
            return values
        return ["users", "orders", "products"]

    def render_sqlalchemy_url(self, dialect_and_connector: str) -> str:
        user = quote_plus(self.postgres_user)
        password = quote_plus(self.postgres_password)
        database = quote_plus(self.postgres_db)
        host = self.postgres_host
        port = self.postgres_port
        return f"{dialect_and_connector}://{user}:{password}@{host}:{port}/{database}"

    @property
    def sqlalchemy_url(self) -> str:
        return self.database_url

    @property
    def async_sqlalchemy_url(self) -> str:
        if self.database_url.startswith("sqlite:///"):
            return self.database_url.replace("sqlite:///", "sqlite+aiosqlite:///")
        return self.database_url.replace("+psycopg2", "+psycopg")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


SETTINGS = get_settings()
