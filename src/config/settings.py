from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # API Keys
    anthropic_api_key: str
    elevenlabs_api_key: str
    flux_api_key: str
    kling_api_key: str
    youtube_client_secret_path: str = "secrets/youtube_client_secret.json"

    # Pipeline behaviour
    max_retries: int = 3
    retry_backoff_base: int = 2
    default_concurrency: int = 3
    default_duration: int = 60
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
