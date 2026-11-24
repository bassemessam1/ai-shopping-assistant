from functools import lru_cache
from urllib.parse import quote_plus
from dotenv import load_dotenv
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()  # LangSmith and OpenAI SDKs read real environment variables

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    environment: str = "local"
    openai_api_key: SecretStr
    database_url: str | None = None          # local: full URL
    db_host: str | None = None               # cloud: parts
    db_port: int = 5432
    db_name: str = "shop"
    db_user: str = "shop_app"
    db_password: SecretStr | None = None
    api_url: str = "http://localhost:8080"
    api_audience: str | None = None          # set in cloud to enable service-to-service auth

    def sqlalchemy_url(self) -> str:
        if self.database_url:
            return self.database_url
        pw = quote_plus(self.db_password.get_secret_value())
        return f"postgresql+psycopg://{self.db_user}:{pw}@{self.db_host}:{self.db_port}/{self.db_name}"

@lru_cache
def get_settings() -> Settings:
    return Settings()