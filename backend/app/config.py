from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://pathfinder:pathfinder@localhost:5432/pathfinder"
    redis_url: str = "redis://localhost:6379/0"
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "pathfinder-raw"
    mlflow_tracking_uri: str = "http://localhost:5001"
    secret_key: str = "change-me-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 480

    sentry_dsn: str = ""
    slack_webhook_url: str = ""
    groq_api_key: str = ""

    # DB pool
    db_pool_size: int = 20
    db_max_overflow: int = 0


settings = Settings()
