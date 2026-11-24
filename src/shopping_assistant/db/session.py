"""Temporary SQLite location. Replaced by the SQLAlchemy engine in step A6."""
from pathlib import Path

# session.py -> db -> shopping_assistant -> src -> repo root
DB_PATH = Path(__file__).resolve().parents[3] / "store.db"


from functools import lru_cache
from sqlalchemy import Engine, create_engine
from shopping_assistant.config import get_settings

@lru_cache
def get_engine() -> Engine:
    # small pool: Cloud SQL shared-core instances allow few connections
    return create_engine(get_settings().sqlalchemy_url(), pool_pre_ping=True,
                         pool_size=3, max_overflow=2)