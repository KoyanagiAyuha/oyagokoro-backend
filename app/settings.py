from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    database_url: str = Field(..., alias="DATABASE_URL")

    # CORS
    cors_origins: str = Field(default="http://localhost:3000", alias="CORS_ORIGINS")

    # Application
    app_env: str = Field(default="local", alias="APP_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # Firebase Auth
    firebase_credentials_file: str | None = Field(default=None, alias="FIREBASE_CREDENTIALS_FILE")
    firebase_project_id: str | None = Field(default=None, alias="FIREBASE_PROJECT_ID")
    firebase_private_key: str | None = Field(default=None, alias="FIREBASE_PRIVATE_KEY")
    firebase_client_email: str | None = Field(default=None, alias="FIREBASE_CLIENT_EMAIL")
    use_auth_mock: bool = Field(default=False, alias="USE_AUTH_MOCK")

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @model_validator(mode="after")
    def _force_disable_mock_in_production(self) -> "Settings":
        if self.app_env == "production" and self.use_auth_mock:
            # 本番環境では USE_AUTH_MOCK を強制無効化（多重防御）
            object.__setattr__(self, "use_auth_mock", False)
        return self


settings = Settings()
