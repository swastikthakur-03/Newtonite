import os
from typing import List
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "Newtonite Operations Management"
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg2://postgres@localhost:5433/newtonite_db"
    )
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "super-secret-newtonite-dev-key-2026-change-in-prod")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours for operational convenience
    ALLOW_SELF_REGISTRATION: bool = os.getenv("ALLOW_SELF_REGISTRATION", "true").lower() in ("true", "1", "yes")
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
    ]

    class Config:
        env_file = ".env"
        extra = "allow"

settings = Settings()
