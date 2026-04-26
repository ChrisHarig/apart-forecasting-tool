from importlib import import_module
from typing import Any

models = import_module("app.db.models")
Base = models.Base


def __getattr__(name: str) -> Any:
    if name in {"SessionLocal", "engine", "get_db", "init_db"}:
        session = import_module("app.db.session")
        return getattr(session, name)
    if name == "models":
        return models
    raise AttributeError(name)


__all__ = ["Base", "SessionLocal", "engine", "get_db", "init_db", "models"]
