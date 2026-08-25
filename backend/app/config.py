from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://fl_user:fl_password@localhost:5432/federated"
    ingest_token: str = "change-me"
    cors_origins: str = (
        "https://federated.near-u-api.org,"
        "http://localhost:5173,"
        "http://localhost:8082"
    )

    @property
    def origins(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
